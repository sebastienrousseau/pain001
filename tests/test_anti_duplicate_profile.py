# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""The cross-record ``anti-duplicate`` scheme profile (issue #183).

Every other bundled profile inspects one row at a time. This one groups
the batch by ``(creditor IBAN, amount, requested execution date)`` and
flags every group of two or more, which is the signature of a payment
keyed in twice. The tests below pin the acceptance criteria from the
issue (both rows flagged pointing at each other, exit code 1, a one-cent
difference is *not* a duplicate) and the composition rule that lets it
run alongside an intra-record profile in one ``--scheme`` spec.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001.api.app import app
from pain001.cli.cli import main
from pain001.constants import TEMPLATES_DIR
from pain001.plugins.registry import registry
from pain001.validation import AntiDuplicateProfile
from pain001.validation.schemes import (
    PROFILES,
    SchemeViolation,
    _duplicate_key,
    _minor_units,
    _split_profile_spec,
    remediation_for,
    validate_scheme,
)

ROOT = Path(__file__).resolve().parents[1]
_TPL = TEMPLATES_DIR / "pain.001.001.03"

#: A SEPA-compliant row carrying every field the duplicate key needs.
BASE_ROW: dict[str, object] = {
    "payment_currency": "EUR",
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "DEUTDEFF",
    "service_level_code": "SEPA",
    "payment_amount": "100.00",
    "requested_execution_date": "2026-09-12",
    "debtor_name": "John Doe",
    "creditor_name": "Acme Corp",
    "remittance_information": "Invoice 12345",
}


def _row(**overrides: object) -> dict[str, object]:
    """Return a copy of :data:`BASE_ROW` with ``overrides`` applied."""
    return {**BASE_ROW, **overrides}


# ---------------------------------------------------------------------------
# Acceptance criteria from the issue
# ---------------------------------------------------------------------------
def test_two_identical_rows_are_both_flagged_pointing_at_each_other() -> None:
    """Both rows carry ``DUP-CREDITOR-DATE`` and name the other's index."""
    result = validate_scheme([_row(), _row()], profile="anti-duplicate")

    assert result.profile == "anti-duplicate"
    assert not result.is_valid
    assert [v.rule for v in result.violations] == [
        "DUP-CREDITOR-DATE",
        "DUP-CREDITOR-DATE",
    ]
    assert [v.index for v in result.violations] == [0, 1]
    assert "row(s) 1" in result.violations[0].message
    assert "row(s) 0" in result.violations[1].message
    assert all(v.field == "creditor_account_IBAN" for v in result.violations)
    assert all(v.severity == "error" for v in result.violations)


def test_one_cent_difference_is_not_a_duplicate() -> None:
    """Exact-key matching: ``100.00`` and ``100.01`` are different payments."""
    result = validate_scheme(
        [_row(), _row(payment_amount="100.01")], profile="anti-duplicate"
    )
    assert result.is_valid
    assert result.violations == []


def test_cli_dry_run_flags_duplicates_and_exits_1() -> None:
    """``--scheme anti-duplicate --dry-run`` reports both rows and exits 1."""
    runner = CliRunner()
    with patch(
        "pain001.cli.cli.load_payment_data",
        return_value=[_row(), _row()],
    ):
        result = runner.invoke(
            main,
            [
                "-t",
                "pain.001.001.03",
                "-m",
                str(_TPL / "template.xml"),
                "-s",
                str(_TPL / "pain.001.001.03.xsd"),
                "-d",
                str(_TPL / "template.csv"),
                "--scheme",
                "anti-duplicate",
                "--dry-run",
            ],
        )
    assert result.exit_code == 1
    assert result.output.count("DUP-CREDITOR-DATE") == 2
    assert "row 0" in result.output
    assert "row 1" in result.output


# ---------------------------------------------------------------------------
# Key construction: what collides, what does not
# ---------------------------------------------------------------------------
def test_amount_formatting_noise_collides() -> None:
    """``100``, ``100.0`` and ``100.000`` all bucket to ``100.00`` for EUR."""
    rows = [
        _row(payment_amount="100"),
        _row(payment_amount="100.0"),
        _row(payment_amount="100.000"),
    ]
    result = validate_scheme(rows, profile="anti-duplicate")
    assert [v.index for v in result.violations] == [0, 1, 2]
    assert "amount 100.00 EUR" in result.violations[0].message


def test_iban_whitespace_and_case_are_normalised() -> None:
    """``"fr14 2004 ..."`` is the same creditor as ``"FR142004..."``."""
    rows = [
        _row(creditor_account_IBAN="fr14 2004 1010 0505 0001 3m02 606"),
        _row(creditor_account_IBAN="FR1420041010050500013M02606"),
    ]
    result = validate_scheme(rows, profile="anti-duplicate")
    assert [v.index for v in result.violations] == [0, 1]


@pytest.mark.parametrize(
    ("currency", "a", "b", "collide"),
    [
        # Zero-minor-unit currency: fractions are rounded away.
        ("JPY", "1000", "1000.4", True),
        ("JPY", "1000", "1001", False),
        # Three-minor-unit currency keeps the third decimal.
        ("KWD", "10.123", "10.1234", True),
        ("KWD", "10.123", "10.124", False),
        # Default two places for anything unlisted.
        ("XYZ", "5.00", "5.004", True),
        ("XYZ", "5.00", "5.01", False),
    ],
)
def test_amounts_bucket_to_the_currency_minor_unit(
    currency: str, a: str, b: str, collide: bool
) -> None:
    """Bucketing follows the ISO 4217 minor unit of the currency."""
    rows = [
        _row(payment_currency=currency, payment_amount=a),
        _row(payment_currency=currency, payment_amount=b),
    ]
    result = validate_scheme(rows, profile="anti-duplicate")
    assert (not result.is_valid) is collide


def test_precision_overrides_widen_or_narrow_the_bucket() -> None:
    """A caller can bucket EUR to whole units (and codes are upper-cased)."""
    coarse = AntiDuplicateProfile(precision_overrides={"eur": 0})
    rows = [_row(payment_amount="100.20"), _row(payment_amount="100.40")]
    assert not coarse.validate(rows).is_valid
    assert AntiDuplicateProfile().validate(rows).is_valid


def test_currency_falls_back_to_the_currency_alias() -> None:
    """Rows with ``currency`` but no ``payment_currency`` still bucket."""
    rows = [
        _row(payment_currency=None, currency="jpy", payment_amount="10"),
        _row(payment_currency=None, currency="JPY", payment_amount="10.3"),
    ]
    result = validate_scheme(rows, profile="anti-duplicate")
    assert not result.is_valid
    assert "amount 10 JPY" in result.violations[0].message


def test_message_omits_currency_when_the_row_has_none() -> None:
    """No trailing space or dangling code when currency is absent."""
    rows = [
        _row(payment_currency=None),
        _row(payment_currency=""),
    ]
    result = validate_scheme(rows, profile="anti-duplicate")
    assert not result.is_valid
    assert "amount 100.00 and execution date" in result.violations[0].message


def test_different_dates_or_creditors_are_different_payments() -> None:
    """Any of the three key fields differing breaks the match."""
    rows = [
        _row(),
        _row(requested_execution_date="2026-09-13"),
        _row(creditor_account_IBAN="DE89370400440532013000"),
    ]
    assert validate_scheme(rows, profile="anti-duplicate").is_valid


@pytest.mark.parametrize(
    "missing",
    [
        {"creditor_account_IBAN": ""},
        {"creditor_account_IBAN": None},
        {"requested_execution_date": ""},
        {"requested_execution_date": None},
        {"payment_amount": ""},
        {"payment_amount": None},
        {"payment_amount": "not-a-number"},
        {"payment_amount": "NaN"},
        {"payment_amount": "Infinity"},
    ],
)
def test_rows_without_a_usable_key_are_skipped(
    missing: dict[str, object],
) -> None:
    """A row that cannot be keyed is never reported (nor crashes)."""
    rows = [_row(**missing), _row(**missing)]
    assert _duplicate_key(rows[0], {}) is None
    assert validate_scheme(rows, profile="anti-duplicate").is_valid


def test_groups_of_three_report_every_partner() -> None:
    """Each row in a group of three names the other two."""
    result = validate_scheme(
        [_row(), _row(), _row()], profile="anti-duplicate"
    )
    assert [v.index for v in result.violations] == [0, 1, 2]
    assert "row(s) 1, 2" in result.violations[0].message
    assert "row(s) 0, 2" in result.violations[1].message
    assert "row(s) 0, 1" in result.violations[2].message


def test_violations_are_reported_in_row_order_across_groups() -> None:
    """Two interleaved duplicate groups come back sorted by row index."""
    other = _row(creditor_account_IBAN="DE89370400440532013000")
    rows = [_row(), other, _row(), other]
    result = validate_scheme(rows, profile="anti-duplicate")
    assert [v.index for v in result.violations] == [0, 1, 2, 3]


def test_minor_units_prefers_override_then_table_then_default() -> None:
    """The precision lookup order is override, ISO table, default two."""
    assert _minor_units("EUR", {"EUR": 4}) == 4
    assert _minor_units("JPY", {}) == 0
    assert _minor_units("KWD", {}) == 3
    assert _minor_units("EUR", {}) == 2
    assert _minor_units("", {}) == 2


def test_empty_batch_is_valid() -> None:
    """No rows, no duplicates."""
    assert validate_scheme([], profile="anti-duplicate").is_valid


# ---------------------------------------------------------------------------
# Composition: --scheme sepa-sct,anti-duplicate
# ---------------------------------------------------------------------------
def test_composed_profiles_report_the_union_of_findings() -> None:
    """Both rulebooks run; the result joins the names and merges by row."""
    rows = [_row(payment_currency="USD"), _row(payment_currency="USD")]
    result = validate_scheme(rows, profile="sepa-sct,anti-duplicate")

    assert result.profile == "sepa-sct,anti-duplicate"
    assert not result.is_valid
    rules = {v.rule for v in result.violations}
    assert "SEPA-CCY" in rules
    assert "DUP-CREDITOR-DATE" in rules
    assert [v.index for v in result.violations] == sorted(
        v.index for v in result.violations
    )


def test_composition_ignores_whitespace_and_repeats() -> None:
    """`` sepa-sct , anti-duplicate, sepa-sct`` runs each profile once."""
    names = _split_profile_spec(" sepa-sct , anti-duplicate, sepa-sct ")
    assert names == ["sepa-sct", "anti-duplicate"]
    result = validate_scheme(
        [_row(), _row()], profile=" sepa-sct , anti-duplicate, sepa-sct "
    )
    assert result.profile == "sepa-sct,anti-duplicate"


def test_single_name_returns_the_profile_result_unchanged() -> None:
    """A one-name spec is exactly the legacy single-profile behaviour."""
    single = validate_scheme([_row(payment_currency="USD")], "sepa-sct")
    assert single.profile == "sepa-sct"
    assert isinstance(single.violations[0], SchemeViolation)


@pytest.mark.parametrize("spec", ["", " , ", "sepa-sct,nope", "nope"])
def test_unknown_or_empty_specs_are_rejected_as_a_whole(spec: str) -> None:
    """An unknown name anywhere in the list raises ValueError naming it."""
    with pytest.raises(ValueError, match="Unknown scheme profile"):
        validate_scheme([_row()], profile=spec)


def test_unknown_name_error_names_the_offending_profile() -> None:
    """The message points at the bad name, not the whole spec."""
    with pytest.raises(ValueError, match="'nope'"):
        validate_scheme([_row()], profile="sepa-sct,nope")


def test_cli_accepts_a_composed_scheme_spec() -> None:
    """``--scheme sepa-sct,anti-duplicate --scheme-format json`` round-trips."""
    runner = CliRunner()
    with patch(
        "pain001.cli.cli.load_payment_data",
        return_value=[_row(), _row()],
    ):
        result = runner.invoke(
            main,
            [
                "-t",
                "pain.001.001.03",
                "-m",
                str(_TPL / "template.xml"),
                "-s",
                str(_TPL / "pain.001.001.03.xsd"),
                "-d",
                str(_TPL / "template.csv"),
                "--scheme",
                "sepa-sct,anti-duplicate",
                "--scheme-format",
                "json",
                "--dry-run",
            ],
        )
    assert result.exit_code == 1
    payload = next(
        json.loads(line)
        for line in result.output.splitlines()
        if line.startswith("{")
    )
    assert payload["profile"] == "sepa-sct,anti-duplicate"
    assert {v["rule"] for v in payload["violations"]} == {"DUP-CREDITOR-DATE"}


def test_rest_api_accepts_the_profile_and_composition() -> None:
    """``POST /api/v1/validate`` with duplicates reports the rule."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/validate",
        json={
            "data_source": "csv",
            "file_path": "tests/data/duplicate_rows.csv",
            "message_type": "pain.001.001.03",
            "scheme": "sepa-sct,anti-duplicate",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert {v["rule"] for v in body["scheme_violations"]} == {
        "DUP-CREDITOR-DATE"
    }
    assert sorted(v["index"] for v in body["scheme_violations"]) == [0, 1]


# ---------------------------------------------------------------------------
# Registration, plugin surface, documentation
# ---------------------------------------------------------------------------
def test_profile_is_registered_and_is_a_plugin() -> None:
    """``PROFILES`` and the plugin registry both expose ``anti-duplicate``."""
    assert isinstance(PROFILES["anti-duplicate"], AntiDuplicateProfile)
    scheme = registry.get_scheme("anti-duplicate")
    assert scheme is not None
    assert scheme.meta.source == "built-in"
    assert "duplicate" in scheme.meta.description.lower()

    result = scheme.validate([_row(), _row()], message_type="pain.001.001.03")
    assert not result.is_valid
    assert [f.row_index for f in result.findings] == [0, 1]
    assert result.findings[0].rule == "DUP-CREDITOR-DATE"
    assert result.findings[0].remediation


def test_rule_has_a_remediation_hint() -> None:
    """``--explain`` has something to say for the new rule."""
    assert remediation_for("DUP-CREDITOR-DATE")


def test_every_documented_profile_list_mentions_anti_duplicate() -> None:
    """CLI help, API models, MCP docstring and the docs all list it."""
    must_mention = [
        ROOT / "pain001" / "cli" / "cli.py",
        ROOT / "pain001" / "api" / "models.py",
        ROOT / "pain001" / "mcp" / "server.py",
        ROOT / "SCHEMES.md",
        ROOT / "README.md",
        ROOT / "docs" / "quickstart.md",
        ROOT / "docs" / "plugins.md",
    ]
    for path in must_mention:
        text = path.read_text(encoding="utf-8")
        assert "anti-duplicate" in text, (
            f"{path.relative_to(ROOT)} omits anti-duplicate"
        )
    assert "DUP-CREDITOR-DATE" in (ROOT / "SCHEMES.md").read_text(
        encoding="utf-8"
    )
