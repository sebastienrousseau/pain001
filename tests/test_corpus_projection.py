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

"""The XML-to-row projection that lets profiles judge corpus files."""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.corpus.rules.projection import rows_from_xml
from pain001.validation.schemes import validate_scheme

MARKET = (
    Path(__file__).resolve().parent.parent
    / "pain001"
    / "corpus"
    / "data"
    / "market"
)


def _market(name: str) -> str:
    return next(MARKET.rglob(name)).read_text(encoding="utf-8")


def test_credit_transfer_rows_carry_both_levels() -> None:
    """PmtInf values are merged into each transaction row."""
    rows = rows_from_xml(
        _market("gb.chaps.property-purchase.pain.001.001.09.xml")
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["payment_currency"] == "GBP" and row["currency"] == "GBP"
    assert row["payment_amount"] == "425000.00"
    assert (
        row["service_level_code"] == "SDVA"
        and row["instruction_priority"] == "HIGH"
    )
    assert row["charge_bearer"] == "SHAR"
    assert row["requested_execution_date"] == "2026-09-12"
    assert row["purpose_code"] == "HLST"
    assert row["creditor_agent_clearing_system"] == "GBDSC"
    assert row["creditor_agent_member_id"] == "309634"
    assert (
        row["creditor_town"] == "Reading" and row["creditor_country"] == "GB"
    )
    assert row["creditor_address_lines"] == "2 High Street"
    assert row["debtor_lei"].startswith("0000")
    assert len(row["uetr"]) == 36
    assert row["remittance_information"] == "Completion 14 Elm Road"
    assert row["end_to_end_id"] == "COMPLETION-2026-0912" == row["payment_id"]
    assert row["id"] == "ELMRD-20260912-0001" and row["nb_of_txs"] == "1"
    assert row["debtor_account_IBAN"].startswith("GB") and row[
        "creditor_account_IBAN"
    ].startswith("GB")
    assert (
        row["debtor_agent_BIC"].endswith("0")
        and row["creditor_agent_BIC"][4:6] == "GB"
    )
    assert "mandate_id" not in row


def test_v03_spellings_project_to_the_same_keys() -> None:
    """BIC and BICOrBEI land in the same keys as BICFI and AnyBIC."""
    v03 = rows_from_xml(_market("de.sepa.sct-salary.pain.001.001.03.xml"))
    v09 = rows_from_xml(_market("de.sepa.sct-salary.pain.001.001.09.xml"))
    assert [r["creditor_agent_BIC"] for r in v03] == [
        r["creditor_agent_BIC"] for r in v09
    ]
    assert v03[1]["creditor_reference"] == "RF18539007547034"
    assert v03[1]["creditor_reference_type"] == "SCOR"
    assert v03[0]["remittance_information"] == "Gehalt September 2026"
    assert v03[0]["debtor_other_id"] == "DE98ZZZ09999999999"
    assert v03[0]["debtor_other_id_scheme"] == "BANK"
    assert (
        v03[0]["category_purpose_code"] == "SALA"
        and v03[0]["batch_booking"] == "true"
    )


def test_direct_debit_rows_swap_sides_and_carry_the_mandate() -> None:
    """For pain.008 the creditor sits on PmtInf and the debtor per transaction."""
    rows = rows_from_xml(_market("nl.sepa.sdd-core.pain.008.001.08.xml"))
    assert len(rows) == 2
    row = rows[0]
    assert row["payment_method"] == "DD" and row["sequence_type"] == "RCUR"
    assert (
        row["local_instrument_code"] == "CORE"
        and row["service_level_code"] == "SEPA"
    )
    assert row["requested_execution_date"] == "2026-10-01"
    assert row["creditor_name"] == "Energie Noord BV"
    assert row["creditor_id"] == "NL98ZZZ123456780001"
    assert (
        row["mandate_id"] == "MNDT-2024-000123"
        and row["date_of_signature"] == "2024-03-01"
    )
    assert (
        row["debtor_name"] == "J. de Vries"
        and rows[1]["debtor_name"] == "Fatima El Amrani"
    )
    assert row["debtor_account_IBAN"].startswith("NL")
    assert validate_scheme(rows, "sepa-sdd").is_valid


def test_inline_document_with_the_long_tail() -> None:
    """Equivalent amounts, proxies, other ids, regulatory reporting, agents."""
    xml = """<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"><CstmrCdtTrfInitn>
<GrpHdr><MsgId>M</MsgId><CreDtTm>2026-01-02T09:00:00</CreDtTm><NbOfTxs>1</NbOfTxs><CtrlSum>10.00</CtrlSum>
<InitgPty><Nm>Init</Nm></InitgPty></GrpHdr>
<PmtInf><PmtInfId>P</PmtInfId><PmtMtd>TRF</PmtMtd><ReqdExctnDt><DtTm>2026-01-03T10:00:00</DtTm></ReqdExctnDt>
<Dbtr><Nm>D</Nm><Id><OrgId><AnyBIC>DEUTDEFF</AnyBIC></OrgId></Id><CtryOfRes>DE</CtryOfRes></Dbtr>
<DbtrAcct><Id><Othr><Id>12345678</Id><SchmeNm><Cd>BBAN</Cd></SchmeNm></Othr></Id><Ccy>GBP</Ccy><Tp><Cd>CACC</Cd></Tp></DbtrAcct>
<DbtrAgt><FinInstnId><Nm>Bank</Nm><Othr><Id>AG1</Id></Othr></FinInstnId></DbtrAgt>
<UltmtDbtr><Nm>UD</Nm></UltmtDbtr>
<CdtTrfTxInf><PmtId><InstrId>I1</InstrId><EndToEndId>E1</EndToEndId></PmtId>
<PmtTpInf><SvcLvl><Prtry>FAST</Prtry></SvcLvl><LclInstrm><Prtry>rtp</Prtry></LclInstrm><CtgyPurp><Prtry>X</Prtry></CtgyPurp></PmtTpInf>
<Amt><EqvtAmt><Amt Ccy="USD">11.00</Amt><CcyOfTrf>EUR</CcyOfTrf></EqvtAmt></Amt>
<IntrmyAgt1><FinInstnId><BICFI>BANKGB2LXXX</BICFI><LEI>5493001KJTIIGC8Y1R12</LEI></FinInstnId></IntrmyAgt1>
<CdtrAgt><FinInstnId><ClrSysMmbId><ClrSysId><Prtry>MY</Prtry></ClrSysId><MmbId>1</MmbId></ClrSysMmbId></FinInstnId></CdtrAgt>
<Cdtr><Nm>C</Nm><Id><PrvtId><Othr><Id>P1</Id><SchmeNm><Prtry>CustNo</Prtry></SchmeNm></Othr></PrvtId></Id></Cdtr>
<CdtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id><Prxy><Tp><Cd>TELE</Cd></Tp><Id>+4917</Id></Prxy></CdtrAcct>
<UltmtCdtr><Nm>UC</Nm></UltmtCdtr>
<InstrForCdtrAgt><Cd>PHOB</Cd></InstrForCdtrAgt><InstrForDbtrAgt>note</InstrForDbtrAgt>
<Purp><Prtry>PP</Prtry></Purp>
<RgltryRptg><DbtCdtRptgInd>BOTH</DbtCdtRptgInd><Dtls><Ctry>AE</Ctry><Cd>SAL</Cd><Inf>/BENEFRES/AE//SAL</Inf></Dtls></RgltryRptg>
<RmtInf><Ustrd>A</Ustrd><Ustrd>B</Ustrd><Strd><CdtrRefInf><Tp><CdOrPrtry><Prtry>OCR</Prtry></CdOrPrtry><Issr>BGC</Issr></Tp><Ref>123</Ref></CdtrRefInf></Strd></RmtInf>
</CdtTrfTxInf></PmtInf></CstmrCdtTrfInitn></Document>"""
    row = rows_from_xml(xml)[0]
    assert (
        row["payment_amount"] == "11.00" and row["payment_currency"] == "EUR"
    )
    assert row["equivalent_amount_currency"] == "USD"
    assert row["requested_execution_date"] == "2026-01-03T10:00:00"
    assert (
        row["debtor_bic"] == "DEUTDEFF"
        and row["debtor_country_of_residence"] == "DE"
    )
    assert (
        row["debtor_account_id"] == "12345678"
        and row["debtor_account_id_scheme"] == "BBAN"
    )
    assert (
        row["debtor_account_currency"] == "GBP"
        and row["debtor_account_type"] == "CACC"
    )
    assert (
        row["debtor_agent_name"] == "Bank"
        and row["debtor_agent_other_id"] == "AG1"
    )
    assert (
        row["ultimate_debtor_name"] == "UD"
        and row["ultimate_creditor_name"] == "UC"
    )
    assert (
        row["service_level_proprietary"] == "FAST"
        and row["local_instrument_proprietary"] == "rtp"
    )
    assert (
        row["category_purpose_proprietary"] == "X"
        and row["purpose_proprietary"] == "PP"
    )
    assert row["intermediary_agent_1_BIC"] == "BANKGB2LXXX" and row[
        "intermediary_agent_1_lei"
    ].startswith("5493")
    assert (
        row["creditor_agent_clearing_system"] == "MY"
        and row["creditor_agent_member_id"] == "1"
    )
    assert (
        row["creditor_other_id"] == "P1"
        and row["creditor_other_id_scheme"] == "CustNo"
    )
    assert (
        row["creditor_account_proxy_type"] == "TELE"
        and row["creditor_account_proxy_id"] == "+4917"
    )
    assert (
        row["instruction_for_creditor_agent"] == "PHOB"
        and row["instruction_for_debtor_agent"] == "note"
    )
    assert (
        row["regulatory_reporting_indicator"] == "BOTH"
        and row["regulatory_reporting_code"] == "SAL"
    )
    assert (
        row["regulatory_reporting_info"] == "/BENEFRES/AE//SAL"
        and row["regulatory_reporting_country"] == "AE"
    )
    assert row["remittance_information"] == "A B"
    assert (
        row["creditor_reference"] == "123"
        and row["creditor_reference_type"] == "OCR"
    )
    assert row["creditor_reference_issuer"] == "BGC"
    assert row["instruction_id"] == "I1" and "uetr" not in row


def test_empty_and_foreign_documents() -> None:
    """No transactions gives no rows; a foreign root raises."""
    empty = '<Document xmlns="urn:x"><CstmrCdtTrfInitn><GrpHdr><MsgId>M</MsgId></GrpHdr></CstmrCdtTrfInitn></Document>'
    assert rows_from_xml(empty) == []
    one = '<Document xmlns="urn:x"><CstmrDrctDbtInitn><PmtInf><DrctDbtTxInf><InstdAmt Ccy="EUR">1.00</InstdAmt></DrctDbtTxInf></PmtInf></CstmrDrctDbtInitn></Document>'
    assert rows_from_xml(one) == [
        {
            "payment_amount": "1.00",
            "payment_currency": "EUR",
            "currency": "EUR",
        }
    ]
    blank = '<Document xmlns="urn:x"><CstmrCdtTrfInitn><PmtInf><CdtTrfTxInf><Amt><InstdAmt Ccy="EUR"> </InstdAmt></Amt><RmtInf/><RgltryRptg/></CdtTrfTxInf></PmtInf></CstmrCdtTrfInitn></Document>'
    assert rows_from_xml(blank) == [{}]
    with pytest.raises(ValueError, match="not a pain.001 or pain.008"):
        rows_from_xml("<Document><Other/></Document>")


def test_equivalent_amount_edge_cases_and_transaction_scheme_id() -> None:
    """A blank equivalent amount, no currency of transfer, a per-transaction scheme id."""
    ns1 = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
    blank = (
        f'<Document xmlns="{ns1}"><CstmrCdtTrfInitn><PmtInf><CdtTrfTxInf>'
        '<Amt><EqvtAmt><Amt Ccy="USD"> </Amt></EqvtAmt></Amt>'
        "</CdtTrfTxInf></PmtInf></CstmrCdtTrfInitn></Document>"
    )
    assert rows_from_xml(blank) == [{}]
    no_ccy = (
        f'<Document xmlns="{ns1}"><CstmrCdtTrfInitn><PmtInf><CdtTrfTxInf>'
        "<Amt><InstdAmt>5.00</InstdAmt></Amt>"
        "</CdtTrfTxInf></PmtInf></CstmrCdtTrfInitn></Document>"
    )
    assert rows_from_xml(no_ccy) == [{"payment_amount": "5.00"}]
    ns8 = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"
    debit = (
        f'<Document xmlns="{ns8}"><CstmrDrctDbtInitn><PmtInf><DrctDbtTxInf>'
        "<DrctDbtTx><CdtrSchmeId><Id><PrvtId><Othr><Id>NL98ZZZ1</Id></Othr>"
        "</PrvtId></Id></CdtrSchmeId></DrctDbtTx>"
        "</DrctDbtTxInf></PmtInf></CstmrDrctDbtInitn></Document>"
    )
    assert rows_from_xml(debit) == [{"creditor_id": "NL98ZZZ1"}]
