# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""IBAN, BIC and LEI checks run on every load, with or without a scheme.

The rows below pass the XSD (its IBAN pattern only tests character
classes), so before 0.0.81 every path wrote the XML. Each test pins one
entry point: the library loaders, ``process_files`` and its streaming
and async forms, ``ValidationService``, the CLI and the REST API, and
the opt-out each of them offers.
"""

from __future__ import annotations

import asyncio
import csv
import time
import xml.etree.ElementTree as ET  # nosec B405 - parses our own output
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001 import PaymentValidationError, process_files
from pain001.api.app import app
from pain001.api.job_manager import JobStatus, job_manager
from pain001.async_adapter import (
    process_files_async,
    process_files_streaming_async,
)
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.core.core import process_files_streaming
from pain001.data.loader import load_payment_data, load_payment_data_streaming
from pain001.validation._identifiers import (
    IDENTIFIER_COLUMNS,
    MAX_LISTED,
    check_identifiers,
    identifier_errors,
    row_errors,
)
from pain001.validation.service import ValidationConfig, ValidationService
from pain001.xml.generate_xml import generate_xml_string

_TYPE = "pain.001.001.03"
_TPL = TEMPLATES_DIR / _TYPE
#: Valid IBAN with its check digits changed: right shape, wrong mod-97.
_BAD_IBAN = "DE88370400440532013000"
#: Right shape for the XSD, but "XQ" is no ISO 3166 country.
_BAD_BIC = "DEUTXQFF"
#: Synthetic LEI (unassigned ``0000`` prefix) with its last check digit
#: changed: right shape for the XSD, wrong MOD 97-10.
_BAD_LEI = "0000006ORRMT71WEV303"
_GOOD_LEI = "0000006ORRMT71WEV302"


def _rows() -> list[dict[str, Any]]:
    with (_TPL / "template.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


#: A per-transaction column: a broken debtor IBAN on one row would be
#: refused first as a second payment information block.
_BAD_COLUMN = "creditor_account_IBAN"


def _bad_rows() -> list[dict[str, Any]]:
    rows = _rows()
    rows[1][_BAD_COLUMN] = _BAD_IBAN
    return rows


def _write(path: Path, rows: list[dict[str, Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def bad_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bundled sample whose second row has a broken IBAN, under cwd."""
    monkeypatch.chdir(tmp_path)
    return _write(tmp_path / "bad.csv", _bad_rows())


def _assert_names_line_not_value(message: str, line: int, column: str) -> None:
    assert f"line {line}, column {column}" in message
    assert _BAD_IBAN not in message
    assert _BAD_BIC not in message


# --- the checks themselves ------------------------------------------------


def test_a_clean_row_has_no_findings() -> None:
    assert all(row_errors(row) == [] for row in _rows())


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("debtor_account_IBAN", _BAD_IBAN, "mod 97"),
        ("creditor_account_IBAN", "DE8937040044053201300", "length for DE"),
        ("debtor_agent_BIC", _BAD_BIC, "ISO 9362"),
        ("creditor_agent_BIC", "DEUTDEF", "ISO 9362"),
        ("creditor_agent_BICFI", "1EUTDEFF", "ISO 9362"),
        ("debtor_account_iban", _BAD_IBAN, "mod 97"),
        ("debtor_lei", _BAD_LEI, "check digits"),
        ("initiator_lei", "0000006ORRMT71WEV30", "20 characters"),
        ("Debtor_LEI", _BAD_LEI, "check digits"),
        ("creditor_agent_lei", _BAD_LEI, "check digits"),
        ("ultimate_creditor_lei", "0000006orrmt71wev302", "upper-case"),
    ],
)
def test_each_identifier_column_is_checked(
    column: str, value: str, reason: str
) -> None:
    findings = row_errors({**_rows()[0], column: value})
    assert len(findings) == 1
    assert findings[0][0] == column
    assert reason in findings[0][1]
    assert value not in findings[0][1]


def test_a_valid_lei_and_lookalike_columns_pass() -> None:
    """Any column named ``*_lei`` is an LEI; ``*lei`` without it is not."""
    row = {
        "debtor_lei": _GOOD_LEI,
        "initiator_lei": f" {_GOOD_LEI} ",
        "creditor_agent_lei": "",
        "lei": _GOOD_LEI,
        "mileage": "not an identifier",
    }
    assert row_errors(row) == []
    assert row_errors({"lei": _BAD_LEI}) == [
        ("lei", row_errors({"debtor_lei": _BAD_LEI})[0][1])
    ]


def test_an_lei_finding_carries_its_own_code() -> None:
    with pytest.raises(PaymentValidationError) as caught:
        check_identifiers([{"debtor_lei": _BAD_LEI}], first_line=2)
    (issue,) = caught.value.errors
    assert (issue.line, issue.column, issue.code) == (
        2,
        "debtor_lei",
        "P001-E022",
    )
    assert _BAD_LEI not in str(caught.value)


def test_empty_values_and_other_columns_are_left_alone() -> None:
    row = {
        "debtor_account_IBAN": "",
        "creditor_account_IBAN": None,
        "debtor_agent_BIC": "   ",
        "charge_account_IBAN": "CHARGE-IBAN-1",
        "forwarding_agent_BIC": "Forwarding-Agent",
        "note": _BAD_IBAN,
    }
    assert row_errors(row) == []


def test_findings_are_indexed_from_start() -> None:
    assert identifier_errors(_bad_rows(), start=10)[0][0] == 11


def test_the_error_lists_rows_and_columns_but_never_values() -> None:
    rows = _bad_rows()
    rows[0]["creditor_agent_BIC"] = _BAD_BIC
    with pytest.raises(PaymentValidationError) as caught:
        check_identifiers(rows)
    message = str(caught.value)
    assert "Invalid identifiers (2)" in message
    _assert_names_line_not_value(message, 1, "creditor_agent_BIC")
    _assert_names_line_not_value(message, 2, _BAD_COLUMN)
    assert "--no-identifier-checks" in message
    assert caught.value.field == "creditor_agent_BIC"


def test_a_long_list_is_cut_short() -> None:
    rows = [{"debtor_account_IBAN": _BAD_IBAN}] * (MAX_LISTED + 3)
    with pytest.raises(PaymentValidationError) as caught:
        check_identifiers(rows)
    message = str(caught.value)
    assert f"line {MAX_LISTED}," in message
    assert f"line {MAX_LISTED + 1}," not in message
    assert "... and 3 more" in message


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_every_rendered_identifier_comes_from_a_checked_column(
    message_type: str,
) -> None:
    """No template renders an IBAN or BIC the checks do not cover."""
    base = TEMPLATES_DIR / message_type
    rows = load_payment_data(str(base / "template.csv"))
    checked = {
        str(value).strip()
        for row in rows
        for key, value in row.items()
        if key in IDENTIFIER_COLUMNS
    }
    xml = generate_xml_string(
        rows,
        message_type,
        str(base / "template.xml"),
        str(base / f"{message_type}.xsd"),
    )
    rendered = [
        (element.tag, element.text)
        for element in ET.fromstring(xml).iter()  # nosec B314
        if element.tag.rsplit("}", 1)[-1] in {"IBAN", "BIC", "BICFI"}
    ]
    assert rendered
    assert all(text in checked for _, text in rendered), rendered


def test_every_rendered_lei_comes_from_a_checked_column() -> None:
    """The ``OrgId/LEI`` elements a template renders are all checked."""
    message_type = "pain.001.001.09"
    base = TEMPLATES_DIR / message_type
    rows = load_payment_data(str(base / "template.csv"))
    rows[0] = {
        **rows[0],
        "initiator_lei": _GOOD_LEI,
        "debtor_lei": "000000MKEGLALP57A130",
    }
    xml = generate_xml_string(
        rows,
        message_type,
        str(base / "template.xml"),
        str(base / f"{message_type}.xsd"),
    )
    rendered = [
        element.text
        for element in ET.fromstring(xml).iter()  # nosec B314
        if element.tag.rsplit("}", 1)[-1] == "LEI"
    ]
    assert sorted(rendered) == sorted([_GOOD_LEI, "000000MKEGLALP57A130"])
    lei_columns = {
        c for c, kind in IDENTIFIER_COLUMNS.items() if kind == "LEI"
    }
    assert lei_columns == {"initiator_lei", "debtor_lei"}
    broken = {**rows[0], "initiator_lei": _BAD_LEI, "debtor_lei": _BAD_LEI}
    assert {column for column, _ in row_errors(broken)} == lei_columns


# --- library --------------------------------------------------------------


def test_load_payment_data_rejects_a_list_and_a_dict() -> None:
    with pytest.raises(PaymentValidationError, match="line 2, column"):
        load_payment_data(_bad_rows())
    with pytest.raises(PaymentValidationError, match="line 1, column"):
        load_payment_data(_bad_rows()[1])


def test_load_payment_data_rejects_a_file(bad_csv: Path) -> None:
    with pytest.raises(PaymentValidationError) as caught:
        load_payment_data(str(bad_csv))
    _assert_names_line_not_value(str(caught.value), 3, _BAD_COLUMN)


def test_load_payment_data_opt_out(bad_csv: Path) -> None:
    count = len(_rows())
    assert len(load_payment_data(str(bad_csv), False)) == count
    assert len(load_payment_data(_bad_rows(), False)) == count


def test_streaming_names_the_row_across_chunks(bad_csv: Path) -> None:
    rows = _rows() + _bad_rows()
    bad = len(_rows()) + 2
    with pytest.raises(PaymentValidationError, match=f"line {bad}, column"):
        list(load_payment_data_streaming(rows, chunk_size=2))
    stream = load_payment_data_streaming(str(bad_csv), chunk_size=1)
    assert next(stream)
    with pytest.raises(PaymentValidationError, match="line 3, column"):
        next(stream)
    chunks = load_payment_data_streaming(
        rows, chunk_size=2, identifier_checks=False
    )
    assert sum(len(chunk) for chunk in chunks) == len(rows)


def _generate(data: Any, tmp_path: Path, **kwargs: Any) -> str:
    return process_files(
        _TYPE,
        str(_TPL / "template.xml"),
        str(_TPL / f"{_TYPE}.xsd"),
        data,
        output_path=str(tmp_path / "out.xml"),
        **kwargs,
    )


def test_process_files_refuses_then_honours_the_opt_out(
    bad_csv: Path, tmp_path: Path
) -> None:
    with pytest.raises(PaymentValidationError, match=_BAD_COLUMN):
        _generate(str(bad_csv), tmp_path)
    assert not (tmp_path / "out.xml").exists()
    written = _generate(str(bad_csv), tmp_path, identifier_checks=False)
    assert Path(written).is_file()


def test_process_files_streaming_and_async(
    bad_csv: Path, tmp_path: Path
) -> None:
    args = (
        _TYPE,
        str(_TPL / "template.xml"),
        str(_TPL / f"{_TYPE}.xsd"),
        str(bad_csv),
    )
    with pytest.raises(PaymentValidationError, match="line 3, column"):
        process_files_streaming(*args, chunk_size=1, output_dir=str(tmp_path))
    with pytest.raises(PaymentValidationError):
        asyncio.run(process_files_async(*args, output_path="a.xml"))
    assert asyncio.run(
        process_files_async(
            *args, output_path="a.xml", identifier_checks=False
        )
    )
    assert asyncio.run(
        process_files_streaming_async(
            *args, output_dir=str(tmp_path), identifier_checks=False
        )
    )


def test_validation_service_honours_pre_validate(bad_csv: Path) -> None:
    config = ValidationConfig(
        xml_message_type=_TYPE,
        xml_template_file_path=str(_TPL / "template.xml"),
        xsd_schema_file_path=str(_TPL / f"{_TYPE}.xsd"),
        data_file_path=str(bad_csv),
    )
    report = ValidationService().validate_all(config)
    assert not report.is_valid
    _assert_names_line_not_value(report.errors[0], 3, _BAD_COLUMN)
    config.pre_validate = False
    assert ValidationService().validate_all(config).is_valid


# --- CLI ------------------------------------------------------------------


def _cli(*args: str) -> Any:
    return CliRunner().invoke(cli, list(args))


@pytest.mark.parametrize("command", ["validate", "generate"])
def test_cli_refuses_a_broken_identifier(command: str, bad_csv: Path) -> None:
    result = _cli(command, "-t", _TYPE, "-d", str(bad_csv))
    assert result.exit_code == 1, result.output
    output = " ".join(result.output.split())
    assert "line 3, column creditor_account_IBAN" in output
    assert _BAD_IBAN not in output


@pytest.mark.parametrize("command", ["validate", "generate"])
def test_cli_opt_out(command: str, bad_csv: Path, tmp_path: Path) -> None:
    result = _cli(
        command, "-t", _TYPE, "-d", str(bad_csv), "--no-identifier-checks"
    )
    assert result.exit_code == 0, result.output
    if command == "generate":
        assert (tmp_path / f"{_TYPE}.xml").exists()


# --- REST -----------------------------------------------------------------


def _post(
    route: str, path: Path, client: TestClient | None = None, **extra: Any
) -> Any:
    body = {
        "data_source": "csv",
        "file_path": str(path),
        "message_type": _TYPE,
    }
    return (client or TestClient(app)).post(route, json={**body, **extra})


@pytest.mark.parametrize("route", ["/api/validate", "/api/generate"])
def test_rest_refuses_then_honours_the_opt_out(
    route: str, bad_csv: Path
) -> None:
    response = _post(route, bad_csv)
    assert response.status_code == 400
    _assert_names_line_not_value(response.json()["detail"], 3, _BAD_COLUMN)
    response = _post(route, bad_csv, identifier_checks=False)
    assert response.status_code == 200
    assert response.json().get("is_valid", True) is True
    assert response.json().get("success", True) is True


def _job(response: Any) -> Any:
    job_id = response.json()["job_id"]
    for _ in range(100):
        job = job_manager.get_job(job_id)
        if job.status in (JobStatus.SUCCESS, JobStatus.FAILED):
            break
        time.sleep(0.05)
    job_manager.cancel_job(job_id)
    return job


def test_rest_async_job_reports_the_row(bad_csv: Path) -> None:
    # One open client: an async job runs on the client's event loop,
    # which a throwaway client closes as soon as the request returns.
    with TestClient(app) as client:
        job = _job(_post("/api/generate/async", bad_csv, client))
        assert job.status == JobStatus.FAILED
        _assert_names_line_not_value(job.error, 3, _BAD_COLUMN)
        job = _job(
            _post(
                "/api/generate/async",
                bad_csv,
                client,
                identifier_checks=False,
                validate_only=True,
            )
        )
        assert job.status == JobStatus.SUCCESS, job.error
