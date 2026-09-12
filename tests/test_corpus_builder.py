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

"""The version-aware builder (ADR-0003, decision 6).

Acceptance from the plan: the same scenario renders valid .03 and .09;
golden tests on three scenarios (the committed market files are the
goldens); the build is idempotent.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

from pain001.corpus import inventory_for
from pain001.corpus.builder import (
    BuildError,
    BuildReport,
    build,
    build_all,
)
from pain001.corpus.registry import load_scenarios, scenario_from
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402

SCENARIOS = {s.id: s for s in load_scenarios()}
CASES = [(s.id, v) for s in SCENARIOS.values() for v in s.versions]


def _base(**overrides):
    doc = {
        "id": "de.sepa.test",
        "family": "sepa-credit-transfer",
        "country": "DE",
        "versions": ["pain.001.001.03", "pain.001.001.09", "pain.001.001.13"],
        "seed": 1,
        "payment": {
            "requested_execution_date": "2026-01-02",
            "debtor": {
                "name": "Debtor",
                "address": {
                    "form": "hybrid",
                    "town": "Berlin",
                    "country": "DE",
                },
            },
            "debtor_account": {"iban": "auto"},
            "debtor_agent": {"bic": "auto"},
        },
        "transactions": [
            {
                "end_to_end_id": "E1",
                "amount": {"ccy": "EUR", "value": "10.00"},
                "creditor": {"name": "Creditor"},
                "creditor_account": {"iban": "auto"},
                "creditor_agent": {"bic": "auto"},
            }
        ],
    }
    doc.update(overrides)
    return doc


def _tags(xml: str, name: str) -> list[str]:
    return re.findall(rf"<{name}>(.*?)</{name}>", xml)


@pytest.mark.parametrize(("scenario_id", "version"), CASES)
def test_golden_market_files_are_the_build_output(
    scenario_id: str, version: str
) -> None:
    """Each committed market file equals a fresh build, byte for byte."""
    scenario = SCENARIOS[scenario_id]
    result = build(scenario, version)
    target = build_corpus.target_for(scenario, version)
    assert target.exists(), f"{target} missing; run scripts/build_corpus.py"
    assert target.read_text(encoding="utf-8") == result.xml
    sidecar = target.with_suffix(".provenance.yaml")
    assert sidecar.read_text(encoding="utf-8") == build_corpus.provenance_for(
        scenario, result
    )
    xsd = DEFAULT_TEMPLATE_REGISTRY.get_template(version).xsd_path
    assert validate_xml_string_via_xsd(result.xml, str(xsd))


def test_same_scenario_renders_v03_and_v09_with_the_right_spelling() -> None:
    """The plan's acceptance: one scenario, two editions, both valid."""
    v03, v09 = build_all(SCENARIOS["gb.chaps.property-purchase"])
    assert (
        v03.version == "pain.001.001.03" and v09.version == "pain.001.001.09"
    )
    assert "<BIC>" in v03.xml and "<BICFI>" not in v03.xml
    assert "<BICFI>" in v09.xml and "<BIC>" not in v09.xml
    assert "<LEI>" not in v03.xml and "<LEI>" in v09.xml
    assert "<UETR>" not in v03.xml and "<UETR>" in v09.xml
    assert "<ReqdExctnDt>2026-09-12</ReqdExctnDt>" in v03.xml
    assert "<ReqdExctnDt>\n        <Dt>2026-09-12</Dt>" in v09.xml
    assert {p for p, _ in v03.report.renamed} >= {
        "/Document/CstmrCdtTrfInitn/PmtInf/DbtrAgt/FinInstnId/BICFI"
    }
    assert [d.rsplit("/", 1)[1] for d in v03.report.dropped] == [
        "LEI",
        "LEI",
        "UETR",
    ]
    assert v09.report.dropped == [] and v09.report.renamed == []
    assert v09.report.wrapped == [
        "/Document/CstmrCdtTrfInitn/PmtInf/ReqdExctnDt"
    ]
    # the referenced party carries one LEI wherever it appears
    assert len(set(_tags(v09.xml, "LEI"))) == 1
    assert _tags(v09.xml, "AdrLine")[0] == "14 Elm Road"


def test_builds_are_idempotent_and_versions_are_listed() -> None:
    """Two builds are identical; an unlisted edition is refused."""
    scenario = SCENARIOS["de.sepa.sct-salary"]
    assert (
        build(scenario, "pain.001.001.13").xml
        == build(scenario, "pain.001.001.13").xml
    )
    with pytest.raises(BuildError, match="does not list pain.008.001.08"):
        build(scenario, "pain.008.001.08")


def test_direct_debit_editions_spell_the_mandate_and_agents() -> None:
    """pain.008 .02 keeps BIC, .08 uses BICFI; the mandate block renders."""
    v02, v08 = build_all(SCENARIOS["nl.sepa.sdd-core"])
    assert "<BIC>" in v02.xml and "<BICFI>" in v08.xml
    assert _tags(v08.xml, "MndtId") == ["MNDT-2024-000123", "MNDT-2025-004567"]
    assert "<SeqTp>RCUR</SeqTp>" in v08.xml and "<LclInstrm>" in v08.xml
    assert "<CdtrSchmeId>" in v08.xml and "<Cd>SEPA</Cd>" in v08.xml
    assert "<CtrlSum>197.40</CtrlSum>" in v08.xml


def test_control_sum_and_counts_are_computed() -> None:
    """NbOfTxs and CtrlSum come from the transactions unless disabled."""
    doc = _base()
    doc["transactions"].append(
        {
            **doc["transactions"][0],
            "end_to_end_id": "E2",
            "amount": {"ccy": "EUR", "value": "0.50"},
        }
    )
    xml = build(doc, "pain.001.001.09").xml
    assert _tags(xml, "NbOfTxs") == ["2", "2"] and _tags(xml, "CtrlSum") == [
        "10.50",
        "10.50",
    ]
    doc["header"] = {
        "control_sum": False,
        "message_id": "M",
        "created": "2026-01-01T00:00:00",
    }
    xml = build(doc, "pain.001.001.09").xml
    assert "<CtrlSum>" not in xml and "<MsgId>M</MsgId>" in xml


def test_address_forms() -> None:
    """Structured, hybrid and unstructured addresses render as expected."""
    address = {
        "street": "Hauptstraße",
        "building_number": "12",
        "post_code": "80331",
        "town": "München",
        "country": "DE",
        "type": "ADDR",
        "floor": "3",
    }
    for form, expect_present, expect_absent in [
        (
            "structured",
            [
                "<StrtNm>Hauptstraße</StrtNm>",
                "<BldgNb>12</BldgNb>",
                "<Flr>3</Flr>",
            ],
            ["<AdrLine>"],
        ),
        (
            "hybrid",
            [
                "<TwnNm>München</TwnNm>",
                "<AdrLine>Hauptstraße 12</AdrLine>",
                "<PstCd>80331</PstCd>",
            ],
            ["<StrtNm>", "<Flr>"],
        ),
        (
            "unstructured",
            [
                "<AdrLine>Hauptstraße 12</AdrLine>",
                "<AdrLine>80331 München</AdrLine>",
                "<Ctry>DE</Ctry>",
            ],
            ["<TwnNm>", "<StrtNm>"],
        ),
    ]:
        doc = _base()
        doc["payment"]["debtor"]["address"] = {**address, "form": form}
        xml = build(doc, "pain.001.001.09").xml
        for text in expect_present:
            assert text in xml, (form, text)
        for text in expect_absent:
            assert text not in xml, (form, text)
    # .03 has no Flr and a plain AdrTp; the fitter drops one and unwraps the other
    doc = _base()
    doc["payment"]["debtor"]["address"] = {**address, "form": "structured"}
    result = build(doc, "pain.001.001.03")
    assert "<AdrTp>ADDR</AdrTp>" in result.xml and "<Flr>" not in result.xml
    assert any(p.endswith("/Flr") for p in result.report.dropped)
    assert any(p.endswith("/AdrTp") for p in result.report.unwrapped)
    assert (
        "<AdrTp>\n            <Cd>ADDR</Cd>"
        in build(doc, "pain.001.001.09").xml
    )
    doc["payment"]["debtor"]["address"] = {
        "form": "unstructured",
        "lines": ["Line 1", "Line 2"],
        "country": "DE",
    }
    assert _tags(build(doc, "pain.001.001.09").xml, "AdrLine") == [
        "Line 1",
        "Line 2",
    ]


def test_party_identification_forms_and_contact() -> None:
    """Org ids with BIC/LEI/other, private ids with birth data, contacts."""
    doc = _base()
    doc["payment"]["debtor"]["id"] = {
        "org": {
            "bic": "DEUTDEFF",
            "lei": "auto",
            "other": [
                {"id": "HRB12345", "scheme": "CUST", "issuer": "AG München"}
            ],
        }
    }
    doc["payment"]["debtor"]["contact"] = {
        "name": "Treasury",
        "email": "t@example.com",
        "phone": "+49-89-1",
        "raw": {"JobTitl": "CFO"},
    }
    doc["payment"]["debtor"]["country_of_residence"] = "DE"
    doc["transactions"][0]["creditor"]["id"] = {
        "private": {
            "birth": {
                "date": "1980-05-04",
                "city": "Berlin",
                "country": "DE",
                "province": "BE",
            },
            "other": [{"id": "X1", "proprietary_scheme": "CustNo"}],
        }
    }
    v09 = build(doc, "pain.001.001.09").xml
    for text in (
        "<AnyBIC>DEUTDEFF</AnyBIC>",
        "<Issr>AG München</Issr>",
        "<Cd>CUST</Cd>",
        "<EmailAdr>t@example.com</EmailAdr>",
        "<JobTitl>CFO</JobTitl>",
        "<CtryOfRes>DE</CtryOfRes>",
        "<BirthDt>1980-05-04</BirthDt>",
        "<PrvcOfBirth>BE</PrvcOfBirth>",
        "<Prtry>CustNo</Prtry>",
    ):
        assert text in v09
    assert re.search(r"<LEI>[A-Z0-9]{18}[0-9]{2}</LEI>", v09)
    v03 = build(doc, "pain.001.001.03")
    assert (
        "<BICOrBEI>DEUTDEFF</BICOrBEI>" in v03.xml
        and "<LEI>" not in v03.xml
        and "<JobTitl>" not in v03.xml
    )


def test_accounts_agents_and_rail_options() -> None:
    """Other-id accounts, proxies, clearing members, branches, service levels."""
    doc = _base()
    doc["payment"]["debtor_account"] = {
        "other": {"id": "12345678", "scheme": "BBAN"},
        "currency": "GBP",
        "name": "Main",
        "type": "CACC",
        "proxy": {"type": "TELE", "id": "+447700900000"},
    }
    doc["payment"]["debtor_agent"] = {
        "clearing": {"system": "GBDSC", "member_id": "040004"},
        "name": "Bank",
        "lei": "auto",
        "branch": {"id": "BR1", "name": "City", "lei": "auto"},
        "address": {"form": "hybrid", "town": "London", "country": "GB"},
        "other": {"id": "AG1"},
    }
    doc["payment"]["type"] = {
        "priority": "HIGH",
        "service_level": ["SEPA", {"proprietary": "URGENT"}],
        "local_instrument": {"code": "INST"},
        "category_purpose": "SUPP",
    }
    doc["header"] = {
        "authorisation": ["AUTH", {"proprietary": "X"}],
        "forwarding_agent": {"bic": "auto", "country": "GB"},
    }
    doc["transactions"][0].update(
        {
            "instruction_id": "I1",
            "charge_bearer": "SLEV",
            "intermediary_agents": [
                {"bic": "auto"},
                {"bic": "auto"},
                {"bic": "auto"},
            ],
            "creditor_agent_account": {"iban": "auto"},
            "ultimate_creditor": {"name": "UC"},
            "ultimate_debtor": {"name": "UD"},
            "instructions_for_creditor_agent": [
                {"code": "PHOB", "text": "call"}
            ],
            "instruction_for_debtor_agent": "note",
            "purpose": {"proprietary": "P1"},
            "exchange_rate": {
                "unit_currency": "EUR",
                "rate": "1.1",
                "type": "SPOT",
                "contract_id": "C1",
            },
        }
    )
    v09 = build(doc, "pain.001.001.09")
    for text in (
        "<Othr>\n          <Id>12345678</Id>",
        "<Prxy>",
        "<Id>+447700900000</Id>",
        "<MmbId>040004</MmbId>",
        "<BrnchId>",
        "<Prtry>URGENT</Prtry>",
        "<Cd>INST</Cd>",
        "<InstrPrty>HIGH</InstrPrty>",
        "<Authstn>",
        "<FwdgAgt>",
        "<IntrmyAgt3>",
        "<CdtrAgtAcct>",
        "<UltmtCdtr>",
        "<Cd>PHOB</Cd>",
        "<InstrInf>call</InstrInf>",
        "<InstrForDbtrAgt>note</InstrForDbtrAgt>",
        "<Prtry>P1</Prtry>",
        "<XchgRate>1.1</XchgRate>",
    ):
        assert text.split("\n")[0] in v09.xml, text
    assert _tags(v09.xml, "Cd").count("SEPA") == 1
    v03 = build(doc, "pain.001.001.03")
    assert "<Prxy>" not in v03.xml
    assert (
        "/Document/CstmrCdtTrfInitn/PmtInf/PmtTpInf/SvcLvl"
        in v03.report.truncated
    )
    assert "<Prtry>URGENT</Prtry>" not in v03.xml


def test_equivalent_amount_remittance_and_raw_merges() -> None:
    """Equivalent amounts, structured remittance, xs:any content and raw."""
    doc = _base()
    tx = doc["transactions"][0]
    tx["equivalent_amount"] = {
        "amount": {"ccy": "USD", "value": "11.00"},
        "currency_of_transfer": "EUR",
    }
    tx["remittance"] = {
        "unstructured": ["Invoice 1", "Invoice 2"],
        "structured": [
            {
                "documents": [
                    {
                        "type": "CINV",
                        "number": "INV-1",
                        "date": "2026-01-01",
                        "issuer": "Me",
                    }
                ],
                "amounts": {
                    "due": {"ccy": "EUR", "value": "10.00"},
                    "remitted": {"ccy": "EUR", "value": "10.00"},
                    "credit_note": {"ccy": "EUR", "value": "0.00"},
                },
                "creditor_reference": {
                    "type": "SCOR",
                    "issuer": "ISO",
                    "reference": "RF18539007547034",
                },
                "invoicer": {"name": "Inv"},
                "invoicee": {"name": "Ee"},
                "additional": ["more"],
                "raw": {
                    "GrnshmtRmt": {
                        "Tp": {"CdOrPrtry": {"Cd": "GNDP"}},
                        "RmtdAmt": {"@Ccy": "EUR", "$": "1.00"},
                    }
                },
            }
        ],
    }
    tx["raw"] = {
        "SplmtryData": {"Envlp": {"Anything": {"Goes": "here"}}},
        "Tax": {"TtlTaxAmt": {"@Ccy": "EUR", "$": "1.90"}},
    }
    doc["payment"]["raw"] = {"PoolgAdjstmntDt": "2026-01-03"}
    doc["header"] = {"raw": {"MsgId": "RAW-WINS"}}
    v09 = build(doc, "pain.001.001.09")
    for text in (
        "<EqvtAmt>",
        "<CcyOfTrf>EUR</CcyOfTrf>",
        "<Ustrd>Invoice 2</Ustrd>",
        "<Nb>INV-1</Nb>",
        '<DuePyblAmt Ccy="EUR">10.00</DuePyblAmt>',
        "<Ref>RF18539007547034</Ref>",
        "<Invcee>",
        "<AddtlRmtInf>more</AddtlRmtInf>",
        "<GrnshmtRmt>",
        "<Goes>here</Goes>",
        '<TtlTaxAmt Ccy="EUR">1.90</TtlTaxAmt>',
        "<PoolgAdjstmntDt>2026-01-03</PoolgAdjstmntDt>",
        "<MsgId>RAW-WINS</MsgId>",
    ):
        assert text in v09.xml, text
    v03 = build(doc, "pain.001.001.03")
    assert "<SplmtryData>" not in v03.xml and "<GrnshmtRmt>" not in v03.xml
    assert any(p.endswith("/SplmtryData") for p in v03.report.dropped)


def test_direct_debit_options() -> None:
    """Amendment flags, pre-notification, scheme ids at transaction level."""
    doc = copy.deepcopy(SCENARIOS["nl.sepa.sdd-core"].data)
    tx = doc["transactions"][0]
    tx["mandate"].update(
        {
            "amendment_indicator": True,
            "electronic_signature": "SIG",
            "first_collection_date": "2024-04-01",
            "final_collection_date": "2027-04-01",
            "frequency": "MNTH",
            "raw": {"AmdmntInfDtls": {"OrgnlMndtId": "OLD-1"}},
        }
    )
    tx["pre_notification"] = {"id": "PRE-1", "date": "2026-09-20"}
    tx["creditor_scheme_id"] = {"ref": "scheme"}
    tx["debtor_agent_account"] = {"iban": "auto"}
    doc["transactions"][1]["mandate"]["amendment_indicator"] = False
    doc["transactions"].append(
        {
            "end_to_end_id": "NO-MANDATE",
            "amount": {"ccy": "EUR", "value": "1.00"},
            "debtor": {"name": "Anon"},
            "debtor_agent": {"bic": "auto"},
            "debtor_account": {"iban": "auto"},
        }
    )
    v08 = build(doc, "pain.008.001.08")
    assert v08.xml.count("<DrctDbtTx>") == 2  # the third has no mandate
    assert "<IBAN>NL" in v08.xml  # an auto account with no party falls back
    for text in (
        "<AmdmntInd>true</AmdmntInd>",
        "<AmdmntInd>false</AmdmntInd>",
        "<OrgnlMndtId>OLD-1</OrgnlMndtId>",
        "<ElctrncSgntr>SIG</ElctrncSgntr>",
        "<PreNtfctnId>PRE-1</PreNtfctnId>",
        "<DbtrAgtAcct>",
    ):
        assert text in v08.xml, text
    assert (
        "<Frqcy>\n              <Tp>MNTH</Tp>" in v08.xml
    )  # .08 wraps the code
    v02 = build(doc, "pain.008.001.02")
    assert "<Frqcy>MNTH</Frqcy>" in v02.xml  # .02 keeps it flat


def test_errors_are_specific() -> None:
    """Unknown refs, accounts without ids, and schema-invalid values."""
    doc = _base()
    doc["payment"]["debtor"] = {"ref": "nobody"}
    with pytest.raises(BuildError, match="party ref 'nobody' is not defined"):
        build(doc, "pain.001.001.09")
    doc = _base()
    doc["payment"]["debtor_account"] = {"currency": "EUR"}
    with pytest.raises(BuildError, match="needs iban or other"):
        build(doc, "pain.001.001.09")
    doc = _base()
    doc["transactions"][0]["creditor_agent"] = {"bic": "NOTABIC"}
    with pytest.raises(
        BuildError,
        match=r"not schema-valid: /Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI",
    ):
        build(doc, "pain.001.001.09")


def test_fitter_edge_cases() -> None:
    """Wrapped values meeting plain slots, unknown wrappers, scalars with no home."""
    doc = _base()
    # a dict with attributes on a simple slot keeps only @ and $
    doc["transactions"][0]["raw"] = {
        "Amt": {"InstdAmt": {"@Ccy": "EUR", "$": "10.00", "Junk": 1}}
    }
    xml = build(doc, "pain.001.001.09").xml
    assert '<InstdAmt Ccy="EUR">10.00</InstdAmt>' in xml
    # a wrapped value with no recognised key on a simple slot is dropped
    doc = _base()
    doc["payment"]["raw"] = {"BtchBookg": {"Weird": "x"}}
    result = build(doc, "pain.001.001.09")
    assert (
        "/Document/CstmrCdtTrfInitn/PmtInf/BtchBookg" in result.report.dropped
    )
    # a scalar on a complex slot with no wrap candidate is dropped
    doc = _base()
    doc["payment"]["raw"] = {"UltmtDbtr": "just a name"}
    result = build(doc, "pain.001.001.09")
    assert (
        "/Document/CstmrCdtTrfInitn/PmtInf/UltmtDbtr/Id"
        in result.report.dropped
    )
    assert "<UltmtDbtr>" not in result.xml
    # an auto account with no party at all takes the scenario country
    doc = _base()
    del doc["transactions"][0]["creditor"]
    assert "<IBAN>DE" in build(doc, "pain.001.001.09").xml
    # a None inside a list is skipped; an empty dict is pruned
    doc = _base()
    doc["payment"]["raw"] = {"ChrgsAcct": {}, "ChrgsAcctAgt": None}
    assert "<ChrgsAcct" not in build(doc, "pain.001.001.09").xml
    # a datetime meets the Dt/DtTm choice
    doc = _base()
    doc["payment"]["requested_execution_date"] = "2026-01-02T10:00:00"
    assert (
        "<DtTm>2026-01-02T10:00:00</DtTm>" in build(doc, "pain.001.001.09").xml
    )
    # booleans serialise as XML booleans
    doc = _base()
    doc["payment"]["batch_booking"] = True
    doc["payment"]["raw"] = {"BtchBookg": True}
    assert "<BtchBookg>true</BtchBookg>" in build(doc, "pain.001.001.09").xml


def test_report_and_result_shapes() -> None:
    """The report starts empty and the inventory namespace is used."""
    report = BuildReport("pain.001.001.09")
    assert report.renamed == [] and report.dropped == []
    result = build(_base(), "pain.001.001.13")
    assert inventory_for("pain.001.001.13").namespace in result.xml
    assert result.xml.startswith(
        "<?xml version='1.0' encoding='UTF-8'?>\n<Document"
    )
    scenario = scenario_from(_base())
    assert (
        build(scenario, "pain.001.001.09").xml
        == build(_base(), "pain.001.001.09").xml
    )
