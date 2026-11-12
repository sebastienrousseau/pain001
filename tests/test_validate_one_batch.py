# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Validation refuses the batches generation refuses.

Generation refuses rows that disagree on a column rendered once in
PmtInf. ``pain001 validate``, ``generate --validate-only`` and the
REST validation endpoints must give the same answer, or a file passes
validation and then fails to generate.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001.api.app import app
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR
from pain001.exceptions import PaymentValidationError
from pain001.validation._one_batch import load_batch, require_generatable
from pain001.xml.batch_consistency import require_one_batch

_TYPE = "pain.001.001.03"
_CONFLICT = "debtor_name (row 1 vs row 2)"


def _rows() -> list[dict[str, Any]]:
    path = TEMPLATES_DIR / _TYPE / "template.csv"
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def mixed_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The bundled sample with a second debtor on row 2, under cwd."""
    monkeypatch.chdir(tmp_path)
    rows = _rows()
    rows[1]["debtor_name"] = "Another Debtor"
    return _write(tmp_path / "mixed.csv", rows)


def test_the_bundled_sample_is_one_batch() -> None:
    require_one_batch(_rows(), _TYPE)


def test_values_are_compared_as_generation_sees_them() -> None:
    """``True`` and ``true`` render the same, so they do not conflict."""
    rows = _rows()
    rows[1]["batch_booking"] = "True"
    require_one_batch(rows, _TYPE)


def test_rows_generation_cannot_normalise_are_left_to_the_schema() -> None:
    """A bad amount is the schema check's finding, not a batch conflict."""
    rows = _rows()
    rows[1]["payment_amount"] = "not a number"
    rows[1]["debtor_name"] = "Another Debtor"
    require_one_batch(rows, _TYPE)


def test_the_preparer_refuses_a_missing_required_field() -> None:
    """Generation's own required fields are checked at validation."""
    rows = _rows()
    for row in rows:
        del row["debtor_account_IBAN"]
    with pytest.raises(PaymentValidationError, match="debtor_account_IBAN"):
        require_generatable(rows, _TYPE)


def test_rows_that_cannot_be_normalised_skip_the_preparer() -> None:
    """A bad amount is the schema check's finding, not the preparer's."""
    rows = _rows()
    rows[0]["payment_amount"] = "not a number"
    for row in rows:
        del row["debtor_account_IBAN"]
    require_generatable(rows, _TYPE)


def test_load_batch_refuses_a_mixed_file(mixed_csv: Path) -> None:
    with pytest.raises(PaymentValidationError, match=r"debtor_name \(row 1"):
        load_batch(str(mixed_csv), _TYPE)


@pytest.mark.parametrize(
    "args",
    [["validate"], ["generate", "--validate-only"]],
)
def test_cli_validation_refuses_a_mixed_file(
    args: list[str], mixed_csv: Path
) -> None:
    result = CliRunner().invoke(
        cli, [*args, "-t", _TYPE, "-d", str(mixed_csv)]
    )
    assert result.exit_code == 1, result.output
    assert _CONFLICT in " ".join(result.output.split())


@pytest.mark.parametrize(
    ("route", "extra"),
    [
        ("/api/validate", {}),
        ("/api/generate", {"validate_only": True}),
    ],
)
def test_rest_validation_refuses_a_mixed_file(
    route: str, extra: dict[str, Any], mixed_csv: Path
) -> None:
    body = {
        "data_source": "csv",
        "file_path": str(mixed_csv),
        "message_type": _TYPE,
        **extra,
    }
    response = TestClient(app).post(route, json=body)
    assert response.status_code == 400, response.text
    assert _CONFLICT in response.json()["detail"]


def test_the_checks_are_public_for_front_ends() -> None:
    """pain001-mcp and other front ends reach both checks by public names."""
    import pain001.validation as validation
    from pain001.xml import batch_consistency

    assert "check_identifiers" in validation.__all__
    assert "identifier_errors" in validation.__all__
    assert validation.check_identifiers is not None
    assert batch_consistency.require_one_batch is require_one_batch
