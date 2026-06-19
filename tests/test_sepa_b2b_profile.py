# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for the SEPA Business-to-Business Direct Debit profile (issue #173).

The B2B rulebook adds two strict requirements on top of the consumer
(``sepa-sdd``) checks:

* the sequence type may only be ``FRST`` or ``RCUR`` (``OOFF`` /
  ``FNAL`` are CORE-only); and
* a ``creditor_id`` (Creditor Identifier) must be present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001 import validate_scheme
from pain001.api.metrics import render_prometheus
from pain001.validation.schemes import (
    PROFILES,
    REMEDIATIONS,
    SepaB2BDirectDebitProfile,
    remediation_for,
)

# A compliant B2B row used as the baseline for the per-rule negative
# tests below. Each negative test takes a copy of this and tweaks one
# field, so the assertion focuses on a single rule id.
COMPLIANT_B2B_ROW: dict = {
    "payment_currency": "EUR",
    "debtor_name": "Acme GmbH",
    "debtor_account_IBAN": "DE89370400440532013000",
    "debtor_agent_BIC": "DEUTDEFF",
    "creditor_name": "BBraun AG",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "BNPAFRPP",
    "creditor_id": "DE98ZZZ09999999999",
    "service_level_code": "SEPA",
    "payment_amount": "50.00",
    "mandate_id": "MNDT-B2B-001",
    "sequence_type": "FRST",
}


def test_profile_is_registered_under_sepa_b2b() -> None:
    """``validate_scheme`` resolves ``sepa-b2b`` to the B2B profile class.

    Criterion 1 of issue #173.
    """
    assert "sepa-b2b" in PROFILES
    assert isinstance(PROFILES["sepa-b2b"], SepaB2BDirectDebitProfile)
    # ``validate_scheme`` accepts the name without raising.
    result = validate_scheme([COMPLIANT_B2B_ROW], profile="sepa-b2b")
    assert result.profile == "sepa-b2b"


def test_compliant_b2b_row_validates_with_zero_violations() -> None:
    """A fully compliant B2B row produces no violations.

    Criterion 2 of issue #173.
    """
    result = validate_scheme([COMPLIANT_B2B_ROW], profile="sepa-b2b")
    assert result.is_valid is True
    assert result.violations == []


@pytest.mark.parametrize("bad", ["OOFF", "FNAL", "TYPO", ""])
def test_disallowed_sequence_type_raises_b2b_seqtp(bad: str) -> None:
    """Sequence types outside FRST/RCUR raise ``B2B-SEQTP``.

    Criterion 3 of issue #173.
    """
    row = {**COMPLIANT_B2B_ROW, "sequence_type": bad}
    result = validate_scheme([row], profile="sepa-b2b")
    seqtp = [v for v in result.violations if v.rule == "B2B-SEQTP"]
    assert seqtp, (
        f"sequence_type {bad!r} should raise B2B-SEQTP; "
        f"got {[v.rule for v in result.violations]}"
    )
    assert seqtp[0].severity == "error"
    assert seqtp[0].field == "sequence_type"


def test_missing_mandate_id_raises_sdd_mndt() -> None:
    """Missing ``mandate_id`` raises ``SDD-MNDT`` (shared SDD rule).

    Criterion 4 of issue #173.
    """
    row = dict(COMPLIANT_B2B_ROW)
    del row["mandate_id"]
    result = validate_scheme([row], profile="sepa-b2b")
    mndt = [v for v in result.violations if v.rule == "SDD-MNDT"]
    assert mndt, "missing mandate_id should raise SDD-MNDT"
    assert mndt[0].field == "mandate_id"


def test_missing_creditor_id_raises_b2b_cdtr_id() -> None:
    """Missing ``creditor_id`` raises the B2B-specific ``B2B-CDTR-ID``.

    Criterion 4 of issue #173.
    """
    row = dict(COMPLIANT_B2B_ROW)
    del row["creditor_id"]
    result = validate_scheme([row], profile="sepa-b2b")
    cid = [v for v in result.violations if v.rule == "B2B-CDTR-ID"]
    assert cid, "missing creditor_id should raise B2B-CDTR-ID"
    assert cid[0].field == "creditor_id"


def test_every_b2b_rule_has_a_remediation_hint() -> None:
    """Every B2B-prefixed rule has a non-empty ``remediation_for`` hint.

    Criterion 5 of issue #173.
    """
    b2b_rules = sorted(r for r in REMEDIATIONS if r.startswith("B2B-"))
    assert b2b_rules, "no B2B-prefixed rules registered"
    for rule in b2b_rules:
        hint = remediation_for(rule)
        assert hint, f"rule {rule!r} has no remediation hint"


def test_cli_api_mcp_enumerations_include_sepa_b2b() -> None:
    """Every documented profile-list mentions ``sepa-b2b``.

    Criterion 6 of issue #173 (CLI, API, MCP enumerations).
    """
    root = Path(__file__).resolve().parents[1]
    must_mention = [
        root / "pain001" / "cli" / "cli.py",
        root / "pain001" / "api" / "models.py",
        root / "pain001" / "mcp" / "server.py",
        root / "SCHEMES.md",
    ]
    for path in must_mention:
        text = path.read_text(encoding="utf-8")
        assert "sepa-b2b" in text, f"{path.relative_to(root)} omits sepa-b2b"


def test_prometheus_metric_reflects_new_profile_count() -> None:
    """``pain001_scheme_profiles`` reflects the new total (5).

    Criterion 6 of issue #173 (the metric reflects the new count).
    """
    import pain001

    metrics_text = render_prometheus(pain001.__version__)
    assert "pain001_scheme_profiles" in metrics_text
    # Find the metric value line.
    lines = [
        line
        for line in metrics_text.splitlines()
        if line.startswith("pain001_scheme_profiles ")
    ]
    assert lines, "pain001_scheme_profiles gauge is missing"
    count = int(lines[0].split()[-1])
    assert count == len(PROFILES)
    assert count >= 5
