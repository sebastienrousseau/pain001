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

"""Faces: outbound projections of pain.001 with honest loss reports (ADR-0005)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.corpus import get_file, list_files
from pain001.faces import (
    MAX_INLINE_BYTES,
    FaceError,
    FaceResult,
    LossReport,
    available_faces,
    detect_version,
    engine,
    list_supported_faces,
    project_face,
    project_face_text,
    register_face,
)
from pain001.faces.berlin_group import project_berlin_group
from pain001.faces.common import (
    account_id,
    address,
    agent_bic,
    payment_information,
    required,
    transactions,
)
from pain001.faces.iso_2018 import name_table, project_iso_2018, snake_case
from pain001.faces.paths import Reader, leaf_paths
from pain001.faces.uk_open_banking import project_uk_open_banking

PAIN001 = [f for f in list_files() if f.version.startswith("pain.001")]
EVERY_ELEMENT_09 = next(
    f.path
    for f in PAIN001
    if f.kind == "coverage"
    and f.version == "pain.001.001.09"
    and f.path.name.startswith("01-transfer-every-element")
)
SALARY_09 = get_file("de.sepa.sct-salary", "pain.001.001.09")
SALARY_03 = get_file("de.sepa.sct-salary", "pain.001.001.03")
SEPA_03 = get_file("be.sepa.sct-supplier", "pain.001.001.03")
TX = "CstmrCdtTrfInitn/PmtInf[0]/CdtTrfTxInf"


def _twin(pmt_inf: dict[str, Any] | list[Any]) -> dict[str, Any]:
    """A minimal twin around one payment information block (or a list)."""
    blocks = pmt_inf if isinstance(pmt_inf, list) else [pmt_inf]
    return {"Document": {"CstmrCdtTrfInitn": {"PmtInf": blocks}}}


def _tx(**extra: Any) -> dict[str, Any]:
    """A transaction with the elements every payment face needs."""
    tx: dict[str, Any] = {
        "PmtId": {"InstrId": "I-1", "EndToEndId": "E-1"},
        "Amt": {"InstdAmt": {"amt": "10.00", "Ccy": "EUR"}},
        "Cdtr": {"Nm": "Creditor"},
        "CdtrAcct": {"Id": {"IBAN": "DE89370400440532013000"}},
    }
    tx.update(extra)
    return tx


def _pmt_inf(*txs: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """A payment information block with an IBAN debtor account."""
    block: dict[str, Any] = {
        "Dbtr": {"Nm": "Debtor"},
        "DbtrAcct": {"Id": {"IBAN": "FR1420041010050500013M02606"}},
        "CdtTrfTxInf": list(txs),
    }
    block.update(extra)
    return block


# --- Paths and the reader --------------------------------------------------


def test_leaf_paths_index_every_array_item() -> None:
    """Two transactions give two distinct sets of paths."""
    twin = _twin(_pmt_inf(_tx(), _tx()))
    paths = leaf_paths(twin)
    assert f"{TX}[0]/Amt/InstdAmt" in paths
    assert f"{TX}[1]/Amt/InstdAmt/@Ccy" in paths
    assert f"{TX}[1]/PmtId/EndToEndId" in paths
    assert leaf_paths({}) == set()


def test_reader_records_only_what_it_returns() -> None:
    """Missing steps and non-text targets record nothing."""
    reader = Reader()
    node = {"A": {"B": "x"}, "L": ["one", {"no": "text"}, "two"]}
    assert reader.text(node, "R", "A", "B") == "x"
    assert reader.text(node, "R", "A", "Z") is None
    assert reader.text(node, "R", "A") is None
    assert reader.text("leaf", "R", "A") is None
    assert reader.amount({"amt": "1", "Ccy": "GBP"}, "R/Amt") == ("1", "GBP")
    assert reader.amount({"amt": "1"}, "R/Amt") is None
    assert reader.texts(node, "R", "L") == ["one", "two"]
    assert reader.texts(node, "R", "A") == []
    assert reader.texts(None, "R", "L") == []
    assert reader.mapped == {
        "R/A/B",
        "R/Amt",
        "R/Amt/@Ccy",
        "R/L[0]",
        "R/L[2]",
    }
    mark = reader.mark()
    reader.text(node, "S", "A", "B")
    reader.rollback(mark)
    assert reader.mapped == set(mark)


# --- Shared navigation -------------------------------------------------------


@pytest.mark.parametrize(
    "twin, count",
    [
        ({}, 0),
        (_twin([]), 0),
        (_twin([{}, {}]), 2),
        ({"Document": {"CstmrCdtTrfInitn": "x"}}, 0),
    ],
)
def test_payment_information_takes_exactly_one_block(
    twin: dict[str, Any], count: int
) -> None:
    """Zero or several blocks are refused with the count."""
    with pytest.raises(FaceError, match=f"this document has {count}"):
        payment_information(twin, "f")


def test_transactions_and_required() -> None:
    """Transactions carry their paths; a missing required value refuses."""
    assert transactions({"CdtTrfTxInf": "bad"}, "P") == []
    assert transactions({"CdtTrfTxInf": [{"a": 1}]}, "P") == [
        ({"a": 1}, "P/CdtTrfTxInf[0]")
    ]
    assert required("v", "f", "X") == "v"
    with pytest.raises(FaceError, match="f: X is required by the target"):
        required(None, "f", "X")


def test_account_id_reads_iban_or_scheme_coded_bban() -> None:
    """Only an Othr identification with scheme code BBAN is a BBAN."""
    bban = {"Id": {"Othr": {"Id": "123", "SchmeNm": {"Cd": "BBAN"}}}}
    other = {"Id": {"Othr": {"Id": "123", "SchmeNm": {"Prtry": "X"}}}}
    no_id = {"Id": {"Othr": {"SchmeNm": {"Cd": "BBAN"}}}}
    reader = Reader()
    assert account_id(reader, {"A": bban}, "P", "A") == ("bban", "123")
    assert reader.mapped == {"P/A/Id/Othr/Id", "P/A/Id/Othr/SchmeNm/Cd"}
    assert account_id(Reader(), {"A": other}, "P", "A") is None
    assert account_id(Reader(), {"A": {"Id": {"Othr": "x"}}}, "P", "A") is None
    empty = Reader()
    assert account_id(empty, {"A": no_id}, "P", "A") is None
    assert empty.mapped == set()
    assert account_id(Reader(), {}, "P", "A") is None


def test_agent_bic_and_address() -> None:
    """BIC is read before .04's BICFI; address lines are optional."""
    reader = Reader()
    assert (
        agent_bic(
            reader, {"Agt": {"FinInstnId": {"BIC": "RQKKDEF0"}}}, "P", "Agt"
        )
        == "RQKKDEF0"
    )
    assert agent_bic(reader, {"Agt": {"FinInstnId": {}}}, "P", "Agt") is None
    party = {"PstlAdr": {"StrtNm": "Main", "Ctry": "DE", "AdrLine": ["L1"]}}
    keys = {"StreetName": "street", "Country": "c", "AddressLine": "lines"}
    assert address(Reader(), party, "P", keys) == {
        "street": "Main",
        "c": "DE",
        "lines": ["L1"],
    }
    assert address(Reader(), {}, "P", {"AddressLine": "lines"}) == {}


# --- UK Open Banking ---------------------------------------------------------


def test_uk_open_banking_projects_one_transaction() -> None:
    """Every mapped field lands where OBWriteDomesticConsent4 defines it."""
    tx = _tx(
        CdtrAgt={"FinInstnId": {"BICFI": "NWBKGB2L"}},
        Cdtr={
            "Nm": "Creditor",
            "PstlAdr": {
                "StrtNm": "High St",
                "Ctry": "GB",
                "AdrLine": ["Flat 1"],
            },
        },
        UltmtCdtr={"Nm": "Ultimate C"},
        UltmtDbtr={"Nm": "Ultimate D"},
        RmtInf={
            "Ustrd": ["Invoice 1"],
            "Strd": [{"CdtrRefInf": {"Ref": "RF18"}}, {}],
        },
    )
    payload, mapped = project_uk_open_banking(_twin(_pmt_inf(tx)))
    initiation = payload["Data"]["Initiation"]
    assert payload["Risk"] == {}
    assert initiation["InstructionIdentification"] == "I-1"
    assert initiation["EndToEndIdentification"] == "E-1"
    assert initiation["InstructedAmount"] == {
        "Amount": "10.00",
        "Currency": "EUR",
    }
    assert initiation["DebtorAccount"] == {
        "SchemeName": "UK.OBIE.IBAN",
        "Identification": "FR1420041010050500013M02606",
        "Name": "Debtor",
    }
    assert initiation["CreditorAccount"]["Name"] == "Creditor"
    assert initiation["CreditorAgent"] == {
        "SchemeName": "UK.OBIE.BICFI",
        "Identification": "NWBKGB2L",
    }
    assert initiation["CreditorPostalAddress"] == {
        "StreetName": "High St",
        "Country": "GB",
        "AddressLine": ["Flat 1"],
    }
    assert initiation["UltimateCreditor"] == {"Name": "Ultimate C"}
    assert initiation["UltimateDebtor"] == {"Name": "Ultimate D"}
    assert initiation["RemittanceInformation"] == {
        "Unstructured": ["Invoice 1"],
        "Structured": [
            {"CreditorReferenceInformation": {"Reference": "RF18"}}
        ],
    }
    assert f"{TX}[0]/RmtInf/Strd[0]/CdtrRefInf/Ref" in mapped


def test_uk_open_banking_bindings_and_minimal_initiation() -> None:
    """A ConsentId makes it OBWriteDomestic2; optional parts stay absent."""
    twin = _twin(_pmt_inf(_tx(), DbtrAcct={"Id": {"Othr": {"Id": "1"}}}))
    payload, _ = project_uk_open_banking(
        twin,
        {
            "ConsentId": "c-1",
            "Risk": {"PaymentContextCode": "TransferToThirdParty"},
        },
    )
    assert list(payload["Data"]) == ["ConsentId", "Initiation"]
    assert payload["Risk"] == {"PaymentContextCode": "TransferToThirdParty"}
    assert "DebtorAccount" not in payload["Data"]["Initiation"]
    with pytest.raises(FaceError, match="Risk binding must be an object"):
        project_uk_open_banking(twin, {"Risk": "x"})


@pytest.mark.parametrize(
    "tx, missing",
    [
        (_tx(PmtId={"EndToEndId": "E"}), "PmtId/InstrId"),
        (_tx(Amt={"EqvtAmt": {}}), "InstdAmt"),
        (_tx(CdtrAcct={"Id": {"Othr": {"Id": "1"}}}), "CdtrAcct/Id/IBAN"),
        (_tx(Cdtr={}), "Cdtr/Nm"),
    ],
)
def test_uk_open_banking_refuses_rather_than_invents(
    tx: dict[str, Any], missing: str
) -> None:
    """A required target field with no source is a refusal naming it."""
    with pytest.raises(FaceError, match=missing):
        project_uk_open_banking(_twin(_pmt_inf(tx)))


def test_uk_open_banking_takes_one_transaction() -> None:
    """A bulk has no domestic payment counterpart."""
    with pytest.raises(FaceError, match="this document has 2"):
        project_uk_open_banking(_twin(_pmt_inf(_tx(), _tx())))


# --- Berlin Group ------------------------------------------------------------


def test_berlin_group_single_payment() -> None:
    """One transaction gives a paymentInitiation_json body."""
    tx = _tx(
        CdtrAgt={"FinInstnId": {"BICFI": "RQKKDEF0", "Nm": "Bank"}},
        Cdtr={
            "Nm": "Creditor",
            "PstlAdr": {
                "StrtNm": "Ring",
                "TwnNm": "Berlin",
                "Ctry": "DE",
                "AdrLine": ["x"],
            },
        },
        RmtInf={"Ustrd": ["first", "second"]},
    )
    block = _pmt_inf(
        tx,
        DbtrAcct={"Id": {"IBAN": "FR1420041010050500013M02606"}, "Ccy": "EUR"},
    )
    payload, mapped = project_berlin_group(_twin(block))
    assert payload == {
        "debtorAccount": {
            "iban": "FR1420041010050500013M02606",
            "currency": "EUR",
        },
        "endToEndIdentification": "E-1",
        "instructedAmount": {"currency": "EUR", "amount": "10.00"},
        "creditorAccount": {"iban": "DE89370400440532013000"},
        "creditorAgent": "RQKKDEF0",
        "creditorAgentName": "Bank",
        "creditorName": "Creditor",
        "creditorAddress": {
            "streetName": "Ring",
            "townName": "Berlin",
            "country": "DE",
        },
        "remittanceInformationUnstructured": "first",
    }
    assert f"{TX}[0]/RmtInf/Ustrd[1]" not in mapped
    assert f"{TX}[0]/Cdtr/PstlAdr/AdrLine[0]" not in mapped


def test_berlin_group_drops_an_address_without_country() -> None:
    """The target requires a country, so a countryless address is a loss."""
    tx = _tx(Cdtr={"Nm": "C", "PstlAdr": {"StrtNm": "Ring"}}, PmtId={})
    payload, mapped = project_berlin_group(_twin(_pmt_inf(tx)))
    assert "creditorAddress" not in payload
    assert "endToEndIdentification" not in payload
    assert f"{TX}[0]/Cdtr/PstlAdr/StrtNm" not in mapped


@pytest.mark.parametrize(
    "date, expected",
    [
        ("2026-01-02", "2026-01-02"),
        ({"Dt": "2026-01-03"}, "2026-01-03"),
        (None, None),
    ],
)
def test_berlin_group_bulk(date: Any, expected: str | None) -> None:
    """Several transactions give a bulk body with every payment."""
    extra: dict[str, Any] = {
        "BtchBookg": "false",
        "PmtTpInf": {"CtgyPurp": {"Cd": "SALA"}},
    }
    if date is not None:
        extra["ReqdExctnDt"] = date
    payload, mapped = project_berlin_group(
        _twin(_pmt_inf(_tx(), _tx(), **extra))
    )
    assert payload["batchBookingPreferred"] is False
    assert payload["categoryPurposeCode"] == "SALA"
    assert payload.get("requestedExecutionDate") == expected
    assert len(payload["payments"]) == 2
    assert f"{TX}[1]/Amt/InstdAmt" in mapped


def test_berlin_group_bulk_invents_no_booking_flag() -> None:
    """Without BtchBookg or a purpose, the bulk leaves both out."""
    payload, _ = project_berlin_group(_twin(_pmt_inf(_tx(), _tx())))
    assert set(payload) == {"debtorAccount", "payments"}


@pytest.mark.parametrize(
    "block, missing",
    [
        (_pmt_inf(_tx(), DbtrAcct={}), "DbtrAcct"),
        (_pmt_inf(), "CdtTrfTxInf"),
        (_pmt_inf(_tx(CdtrAcct={})), "CdtrAcct"),
        (_pmt_inf(_tx(Cdtr={})), "Cdtr/Nm"),
    ],
)
def test_berlin_group_refuses_rather_than_invents(
    block: dict[str, Any], missing: str
) -> None:
    """Required target fields with no source are refusals."""
    with pytest.raises(FaceError, match=missing):
        project_berlin_group(_twin(block))


# --- ISO 2018 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "name, snake",
    [
        ("GroupHeader", "group_header"),
        ("BICFI", "bicfi"),
        ("AnyBIC", "any_bic"),
        ("UETR", "uetr"),
        (
            "CreditTransferTransactionInformation",
            "credit_transfer_transaction_information",
        ),
    ],
)
def test_snake_case(name: str, snake: str) -> None:
    """Runs of capitals stay one word."""
    assert snake_case(name) == snake


def test_name_table_has_provenance() -> None:
    """The table records its reports and read date, and every gap's reason."""
    table = name_table()
    assert table["source"].startswith("ISO 20022 Message Definition Reports")
    assert table["reports"] and table["read_date"]
    assert table["names"]["GrpHdr"] == "GroupHeader"
    assert set(table["unresolved"]) >= {"BIC", "BICOrBEI"}
    assert all(table["unresolved"].values())


def test_iso_2018_projects_names_and_amounts() -> None:
    """A .09 document maps with no loss but the schema-free envelope."""
    result = project_face(SALARY_09, face="iso_2018")
    header = result.payload["group_header"]
    assert {"message_identification", "creation_date_time"} <= set(header)
    tx = result.payload["payment_information"][0][
        "credit_transfer_transaction_information"
    ][0]
    assert set(tx["amount"]["instructed_amount"]) == {"amount", "currency"}
    assert result.loss_report.is_lossless


def test_iso_2018_leaves_unresolved_tags_to_the_loss_report() -> None:
    """pain.001.001.03's BIC has no MDR name, so it is a reported loss."""
    result = project_face(SEPA_03, face="iso_2018")
    assert any(p.endswith("/BIC") for p in result.loss_report.unmapped_paths)
    assert not result.loss_report.is_lossless
    with pytest.raises(FaceError, match="no CstmrCdtTrfInitn"):
        project_iso_2018({})


# --- Engine ------------------------------------------------------------------


def test_registry_lists_faces_and_bindings() -> None:
    """Each face states the bindings it accepts."""
    assert {"berlin_group", "iso_2018", "uk_open_banking"} <= set(
        available_faces()
    )
    faces = {f["name"]: f for f in list_supported_faces()}
    assert faces["uk_open_banking"]["bindings"] == ["ConsentId", "Risk"]
    assert faces["berlin_group"]["bindings"] == []


def test_detect_version() -> None:
    """The edition comes from the namespace."""
    assert detect_version(SALARY_09) == "pain.001.001.09"
    with pytest.raises(FaceError, match="could not detect"):
        detect_version("<Document/>")


def test_loss_report_is_per_occurrence() -> None:
    """A face that drops the second transaction cannot pass as lossless.

    The engine used to compare unindexed paths, so mapping the first of
    two transactions marked the second's identical paths as mapped.
    """

    def first_only(
        twin: dict[str, Any], _b: dict[str, Any] | None
    ) -> tuple[dict[str, Any], set[str]]:
        return {}, {p for p in leaf_paths(twin) if "CdtTrfTxInf[1]" not in p}

    register_face("first_only_test", first_only, "test face")
    try:
        result = project_face(SALARY_09, face="first_only_test")
    finally:
        engine._REGISTRY.pop("first_only_test")
    unmapped = result.loss_report.unmapped_paths
    assert unmapped and all("CdtTrfTxInf[1]" in p for p in unmapped)
    assert not result.loss_report.is_lossless


def test_project_face_inputs_and_errors(tmp_path: Path) -> None:
    """Paths, path strings and inline XML all work; bad input is refused."""
    xml_file = tmp_path / "p.xml"
    xml_file.write_text(SALARY_09, encoding="utf-8")
    by_path = project_face(xml_file, face="berlin_group")
    by_str = project_face(str(xml_file), face="berlin_group")
    assert (
        by_path.payload
        == by_str.payload
        == project_face(SALARY_09, face="berlin_group").payload
    )
    assert by_path.version == "pain.001.001.09"
    with pytest.raises(FaceError, match="unknown face 'nope'"):
        project_face(SALARY_09, face="nope")
    with pytest.raises(FaceError, match="unknown binding.*accepted: none"):
        project_face(SALARY_09, face="berlin_group", bindings={"x": 1})
    with pytest.raises(FaceError, match="failed to generate ISO JSON twin"):
        project_face(
            "<invalid>xml", face="iso_2018", version="pain.001.001.03"
        )


def test_project_face_text_matches_project_face() -> None:
    """Inline XML from a client gives the same result as the library call."""
    expected = project_face(SALARY_09, face="berlin_group").to_dict()
    assert (
        project_face_text(SALARY_09, face="berlin_group").to_dict() == expected
    )


def test_project_face_text_never_reads_a_path(tmp_path: Path) -> None:
    """A string naming a server file is refused, not read."""
    xml_file = tmp_path / "p.xml"
    xml_file.write_text(SALARY_09, encoding="utf-8")
    with pytest.raises(FaceError, match="expected the pain.001 document"):
        project_face_text(str(xml_file), face="berlin_group")
    not_text: Any = xml_file
    with pytest.raises(FaceError, match="expected the pain.001 document"):
        project_face_text(not_text, face="berlin_group")


@pytest.mark.parametrize(
    "xml",
    [
        '<!DOCTYPE d [<!ENTITY a "aaaa">]><d>&a;</d>',
        '<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><d>&x;</d>',
    ],
    ids=["internal-entity", "external-entity"],
)
def test_project_face_text_refuses_entities(xml: str) -> None:
    """Entity declarations (billion laughs, XXE) never reach the parser."""
    with pytest.raises(FaceError, match="refused XML"):
        project_face_text(xml, face="iso_2018")


def test_project_face_text_refuses_bad_input() -> None:
    """Malformed, oversized and wrongly typed input is refused."""
    with pytest.raises(FaceError, match="not well-formed XML"):
        project_face_text("<a><b></a>", face="iso_2018")
    oversized = "<a>" + "x" * MAX_INLINE_BYTES + "</a>"
    with pytest.raises(FaceError, match="exceeds 10 MiB"):
        project_face_text(oversized, face="iso_2018")
    not_an_object: Any = ["ConsentId"]
    with pytest.raises(FaceError, match="bindings must be a JSON object"):
        project_face_text(
            SALARY_09, face="uk_open_banking", bindings=not_an_object
        )
    with pytest.raises(FaceError, match="unknown face 'nope'"):
        project_face_text(SALARY_09, face="nope")


@pytest.mark.parametrize(
    "corpus_file", PAIN001, ids=lambda f: f"{f.kind}:{f.path.name}"
)
@pytest.mark.parametrize(
    "face", ["uk_open_banking", "berlin_group", "iso_2018"]
)
def test_every_corpus_file_projects_or_is_refused(
    corpus_file: Any, face: str
) -> None:
    """No face crashes on the corpus, and the loss report partitions it."""
    xml = corpus_file.path.read_text(encoding="utf-8")
    try:
        result = project_face(xml, face=face, version=corpus_file.version)
    except FaceError as exc:
        assert str(exc).startswith(face)
        return
    report = result.loss_report
    assert not set(report.mapped_paths) & set(report.unmapped_paths)
    assert (
        len(report.mapped_paths) + len(report.unmapped_paths)
        == report.total_source_elements
    )


def test_berlin_group_bulk_from_the_corpus() -> None:
    """A real salary run (.03, plain execution date) becomes a bulk."""
    result = project_face(SALARY_03, face="berlin_group")
    assert len(result.payload["payments"]) > 1
    assert "requestedExecutionDate" in result.payload


# --- Models ------------------------------------------------------------------


def test_loss_report_and_result_serialisation() -> None:
    """Ratios, flags and JSON shapes."""
    report = LossReport("f", 4, ("a", "b", "c"), ("d",))
    assert report.loss_ratio == 0.25 and not report.is_lossless
    assert report.to_dict()["unmapped_count"] == 1
    assert LossReport("f", 0, (), ()).loss_ratio == 0.0
    result = FaceResult("f", "pain.001.001.09", {"k": "v"}, report)
    assert result.to_dict()["loss_report"]["mapped_count"] == 3
    assert json.loads(result.to_json()) == {"k": "v"}


# --- CLI ---------------------------------------------------------------------


def test_face_cli(tmp_path: Path) -> None:
    """``pain001 face`` writes payloads, loss reports and clear errors."""
    runner = CliRunner()
    out_json = tmp_path / "out.json"
    bindings = tmp_path / "bindings.json"
    bindings.write_text(
        json.dumps({"ConsentId": "consent-cli-999"}), encoding="utf-8"
    )
    res = runner.invoke(
        cli,
        [
            "face",
            str(EVERY_ELEMENT_09),
            "--face",
            "uk_open_banking",
            "--bindings",
            str(bindings),
            "--output",
            str(out_json),
            "--loss-report",
        ],
    )
    assert res.exit_code == 0, res.output
    assert "Wrote uk_open_banking face to" in res.output
    assert "Face Loss Report:" in res.output
    assert (
        json.loads(out_json.read_text(encoding="utf-8"))["Data"]["ConsentId"]
        == "consent-cli-999"
    )

    xml_path = tmp_path / "salary.xml"
    xml_path.write_text(SALARY_09, encoding="utf-8")
    res = runner.invoke(cli, ["face", str(xml_path), "--face", "iso_2018"])
    assert res.exit_code == 0 and "group_header" in res.output

    for content, message in (
        ("invalid json", "Error loading bindings"),
        ("[1]", "expected a JSON object"),
    ):
        bad = tmp_path / "bad.json"
        bad.write_text(content, encoding="utf-8")
        res = runner.invoke(
            cli, ["face", str(xml_path), "--bindings", str(bad)]
        )
        assert res.exit_code == 1 and message in res.output

    res = runner.invoke(
        cli, ["face", str(xml_path), "--face", "uk_open_banking"]
    )
    assert res.exit_code == 1 and "Face projection error" in res.output
