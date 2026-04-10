from typing import Any, cast

from pain001.camt053 import parse_camt053_statement
from pain001.pain002 import parse_pain002_report
from pain001.xml.generate_xml import generate_xml_string
from pain001.csv.load_csv_data import load_csv_data


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
