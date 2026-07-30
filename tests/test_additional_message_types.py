# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from pain001.camt053 import parse_camt053_statement
from pain001.csv.load_csv_data import load_csv_data
from pain001.exceptions import DataSourceError, SchemaValidationError
from pain001.pain002 import parse_pain002_report
from pain001.xml.generate_xml import generate_xml_string

PAIN002_SAMPLE = "pain001/test_fixtures/pain002_sample.xml"
CAMT053_SAMPLE = "pain001/test_fixtures/camt053_sample.xml"
ANY_XSD = "pain001/test_fixtures/template.xsd"


def test_parse_pain002_report_fixture() -> None:
    report = cast(
        dict[str, Any],
        parse_pain002_report("pain001/test_fixtures/pain002_sample.xml"),
    )

    assert report["message_id"] == "STAT-001"
    assert report["original_message_id"] == "PMT-BATCH-001"
    assert report["group_status"] == "PART"
    assert report["payment_statuses"][0]["transaction_status"] == "RJCT"
    assert report["payment_statuses"][0]["status_reason"] == "AC04"


def test_parse_camt053_statement_fixture() -> None:
    statement = cast(
        dict[str, Any],
        parse_camt053_statement("pain001/test_fixtures/camt053_sample.xml"),
    )

    assert statement["statement_id"] == "STMT-001"
    assert statement["iban"] == "DE89370400440532013000"
    assert statement["entries"][0]["currency"] == "EUR"
    assert statement["entries"][0]["remittance_information"].startswith(
        "Incoming transfer"
    )


def test_generate_pain008_string_from_template_fixture() -> None:
    version = "pain.008.001.02"
    data = load_csv_data(f"pain001/templates/{version}/template.csv")
    xml = generate_xml_string(
        data,
        version,
        f"pain001/templates/{version}/template.xml",
        f"pain001/templates/{version}/{version}.xsd",
    )

    assert "CstmrDrctDbtInitn" in xml
    assert "MANDATE-001" in xml
    assert "SeqTp" in xml


def test_parse_pain002_rejects_missing_xml_path(tmp_path: Path) -> None:
    with pytest.raises(DataSourceError, match="Invalid pain.002 XML path"):
        parse_pain002_report(str(tmp_path / "missing.xml"))


def test_parse_camt053_rejects_missing_xml_path(tmp_path: Path) -> None:
    with pytest.raises(DataSourceError, match="Invalid camt.053 XML path"):
        parse_camt053_statement(str(tmp_path / "missing.xml"))


def test_parse_pain002_rejects_missing_xsd_path(tmp_path: Path) -> None:
    with pytest.raises(DataSourceError, match="Invalid pain.002 XSD path"):
        parse_pain002_report(PAIN002_SAMPLE, str(tmp_path / "missing.xsd"))


def test_parse_camt053_rejects_missing_xsd_path(tmp_path: Path) -> None:
    with pytest.raises(DataSourceError, match="Invalid camt.053 XSD path"):
        parse_camt053_statement(CAMT053_SAMPLE, str(tmp_path / "missing.xsd"))


def test_parse_pain002_schema_validation_failure() -> None:
    with patch(
        "pain001.pain002.parser.validate_via_xsd",
        autospec=True,
        return_value=False,
    ):
        with pytest.raises(SchemaValidationError):
            parse_pain002_report(PAIN002_SAMPLE, ANY_XSD)


def test_parse_camt053_schema_validation_failure() -> None:
    with patch(
        "pain001.camt053.parser.validate_via_xsd",
        autospec=True,
        return_value=False,
    ):
        with pytest.raises(SchemaValidationError):
            parse_camt053_statement(CAMT053_SAMPLE, ANY_XSD)


def test_parse_pain002_schema_validation_success() -> None:
    with patch(
        "pain001.pain002.parser.validate_via_xsd",
        autospec=True,
        return_value=True,
    ):
        report = parse_pain002_report(PAIN002_SAMPLE, ANY_XSD)
    assert report["message_id"] == "STAT-001"


def test_parse_pain002_rejects_malformed_xml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_text("<Document><unclosed", encoding="utf-8")
    with pytest.raises(DataSourceError, match="Unable to parse pain.002"):
        parse_pain002_report(str(bad))


def test_parse_camt053_rejects_malformed_xml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_text("<Document><unclosed", encoding="utf-8")
    with pytest.raises(DataSourceError, match="Unable to parse camt.053"):
        parse_camt053_statement(str(bad))


def test_parse_pain002_rejects_wrong_document_type() -> None:
    with pytest.raises(DataSourceError, match="not a pain.002"):
        parse_pain002_report(CAMT053_SAMPLE)


def test_parse_camt053_rejects_wrong_document_type() -> None:
    with pytest.raises(DataSourceError, match="not a camt.053"):
        parse_camt053_statement(PAIN002_SAMPLE)


def test_parse_camt053_without_namespace(tmp_path: Path) -> None:
    xml = tmp_path / "plain.xml"
    xml.write_text(
        "<Document><BkToCstmrStmt><Stmt><Id>S1</Id>"
        '<Ntry><Amt Ccy="EUR">5.00</Amt></Ntry>'
        "</Stmt></BkToCstmrStmt></Document>",
        encoding="utf-8",
    )
    statement = cast(dict[str, Any], parse_camt053_statement(str(xml)))
    assert statement["statement_id"] == "S1"
    entries = cast(list[dict[str, str]], statement["entries"])
    assert entries[0]["currency"] == "EUR"
    assert entries[0]["remittance_information"] == ""
