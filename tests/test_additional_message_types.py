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


@pytest.mark.parametrize("version", ["pain.008.001.02", "pain.008.001.08"])
def test_pain008_columns_name_the_direct_debit_roles(version: str) -> None:
    """creditor_* columns render as the collector, debtor_* as the payer (#346).

    In a direct debit the creditor collects and the debtor pays, so the
    ``creditor_*`` columns fill ``Cdtr``/``CdtrAcct``/``CdtrAgt`` and the
    ``debtor_*`` columns fill ``Dbtr``/``DbtrAcct``/``DbtrAgt``.
    """
    from lxml import etree

    row = {
        "id": "DD-ROLES-1",
        "date": "2026-01-15T10:30:00",
        "nb_of_txs": "1",
        "ctrl_sum": "100.00",
        "initiator_name": "Landlord Ltd",
        "payment_information_id": "PMT-ROLES-1",
        "payment_method": "DD",
        "batch_booking": "false",
        "service_level_code": "SEPA",
        "sequence_type": "RCUR",
        "requested_execution_date": "2026-01-20",
        "creditor_name": "Landlord Ltd",
        "creditor_account_IBAN": "DE89370400440532013000",
        "creditor_agent_BIC": "DEUTDEFFXXX",
        "charge_bearer": "SLEV",
        "payment_id": "E2E-ROLES-1",
        "payment_amount": "100.00",
        "currency": "EUR",
        "payment_currency": "EUR",
        "debtor_name": "Tenant One",
        "debtor_account_IBAN": "FR1420041010050500013M02606",
        "debtor_agent_BIC": "BNPAFRPPXXX",
        "remittance_information": "Rent January",
        "mandate_id": "MANDATE-ROLES-1",
        "date_of_signature": "2025-11-15",
        "forwarding_agent_BIC": "DEUTDEFFXXX",
    }
    xml = generate_xml_string(
        [row],
        version,
        f"pain001/templates/{version}/template.xml",
        f"pain001/templates/{version}/{version}.xsd",
    )
    ns = {"p": f"urn:iso:std:iso:20022:tech:xsd:{version}"}
    root = etree.fromstring(xml.encode("utf-8"))
    pmt = root.find("p:CstmrDrctDbtInitn/p:PmtInf", ns)
    tx = pmt.find("p:DrctDbtTxInf", ns)

    assert pmt.findtext("p:Cdtr/p:Nm", namespaces=ns) == "Landlord Ltd"
    assert (
        pmt.findtext("p:CdtrAcct/p:Id/p:IBAN", namespaces=ns)
        == "DE89370400440532013000"
    )
    assert "DEUTDEFFXXX" in etree.tostring(pmt.find("p:CdtrAgt", ns)).decode()
    assert tx.findtext("p:Dbtr/p:Nm", namespaces=ns) == "Tenant One"
    assert (
        tx.findtext("p:DbtrAcct/p:Id/p:IBAN", namespaces=ns)
        == "FR1420041010050500013M02606"
    )
    assert "BNPAFRPPXXX" in etree.tostring(tx.find("p:DbtrAgt", ns)).decode()


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


def test_parse_pain002_reads_transaction_status() -> None:
    """Transaction-level status and reason codes are lifted onto the record."""
    report = cast(
        dict[str, Any],
        parse_pain002_report("pain001/test_fixtures/pain002_sample.xml"),
    )
    first = report["payment_statuses"][0]
    assert first["original_end_to_end_id"] == "PaymentID6789"
    assert first["transaction_status"] == "RJCT"


def test_find_text_returns_empty_for_missing_paths() -> None:
    from xml.etree import ElementTree as ET

    from pain001.pain002.parser import _find_text

    root = ET.fromstring("<a><b><c>x</c></b></a>")
    assert _find_text(root, "", "b/c") == "x"
    assert _find_text(root, "", "b/missing") == ""
    assert _find_text(root, "", "missing/c") == ""
