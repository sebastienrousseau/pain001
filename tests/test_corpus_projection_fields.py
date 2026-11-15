# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Every element the projection reads lands on its own row key.

Two hand-built documents, a credit transfer and a direct debit, carry
each element the projection knows, with a distinct value, and the
alternative spellings (``BIC`` for ``BICFI``, ``Prtry`` for ``Cd``,
``BICOrBEI`` for ``AnyBIC``) on a second transaction. The rows are
compared whole, so a value read from the wrong element, under the wrong
key, or not at all is a failure.
"""

from __future__ import annotations

import pytest

from pain001.corpus.rules.projection import rows_from_xml

CT_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
DD_NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"

CREDIT_TRANSFER = f"""<Document xmlns="{CT_NS}"><CstmrCdtTrfInitn>
<GrpHdr><MsgId>MSG1</MsgId><CreDtTm>2026-01-02T09:00:00</CreDtTm>
<NbOfTxs>2</NbOfTxs><CtrlSum>30.00</CtrlSum>
<InitgPty><Nm>Initiator</Nm></InitgPty></GrpHdr>
<PmtInf><PmtInfId>PMT1</PmtInfId><PmtMtd>TRF</PmtMtd>
<BtchBookg>true</BtchBookg><ReqdExctnDt><Dt>2026-01-03</Dt></ReqdExctnDt>
<PmtTpInf><InstrPrty>HIGH</InstrPrty><SvcLvl><Cd>SEPA</Cd></SvcLvl>
<LclInstrm><Cd>INST</Cd></LclInstrm><CtgyPurp><Cd>SUPP</Cd></CtgyPurp>
<SeqTp>OOFF</SeqTp></PmtTpInf>
<Dbtr><Nm>Debtor Ltd</Nm><PstlAdr><StrtNm>Main Street</StrtNm>
<PstCd>10115</PstCd><TwnNm>Berlin</TwnNm><Ctry>DE</Ctry>
<AdrLine>Line 1</AdrLine><AdrLine>Line 2</AdrLine></PstlAdr>
<Id><OrgId><LEI>5493001KJTIIGC8Y1R12</LEI><Othr><Id>ORG1</Id>
<SchmeNm><Cd>CUST</Cd></SchmeNm></Othr></OrgId></Id>
<CtryOfRes>AT</CtryOfRes></Dbtr>
<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id><Ccy>EUR</Ccy>
<Tp><Prtry>OWN</Prtry></Tp><Prxy><Tp><Prtry>ALIAS</Prtry></Tp>
<Id>debtor@example.org</Id></Prxy></DbtrAcct>
<DbtrAgt><FinInstnId><BICFI>COBADEFFXXX</BICFI><ClrSysMmbId><ClrSysId>
<Cd>DEBLZ</Cd></ClrSysId><MmbId>37040044</MmbId></ClrSysMmbId>
<LEI>5493001KJTIIGC8Y1R12</LEI><Nm>Debtor Bank</Nm>
<Othr><Id>DAG</Id></Othr></FinInstnId></DbtrAgt>
<UltmtDbtr><Nm>Ultimate Debtor</Nm></UltmtDbtr><ChrgBr>SLEV</ChrgBr>
<CdtTrfTxInf><PmtId><InstrId>INS1</InstrId><EndToEndId>E2E1</EndToEndId>
<UETR>8a562c67-ca16-48ba-b074-65581be6f001</UETR></PmtId>
<PmtTpInf><SvcLvl><Prtry>TXSVC</Prtry></SvcLvl></PmtTpInf>
<Amt><InstdAmt Ccy="EUR">10.00</InstdAmt></Amt><ChrgBr>SHAR</ChrgBr>
<IntrmyAgt1><FinInstnId><BICFI>DEUTDEFFXXX</BICFI></FinInstnId></IntrmyAgt1>
<IntrmyAgt2><FinInstnId><BICFI>BNPAFRPPXXX</BICFI></FinInstnId></IntrmyAgt2>
<IntrmyAgt3><FinInstnId><BICFI>NWBKGB2LXXX</BICFI></FinInstnId></IntrmyAgt3>
<CdtrAgt><FinInstnId><BICFI>INGBNL2AXXX</BICFI></FinInstnId></CdtrAgt>
<Cdtr><Nm>Creditor BV</Nm><PstlAdr><TwnNm>Amsterdam</TwnNm><Ctry>NL</Ctry>
</PstlAdr><Id><OrgId><AnyBIC>INGBNL2A</AnyBIC></OrgId></Id></Cdtr>
<CdtrAcct><Id><Othr><Id>ACC2</Id><SchmeNm><Prtry>LOCAL</Prtry></SchmeNm>
</Othr></Id><Tp><Cd>CACC</Cd></Tp></CdtrAcct>
<UltmtCdtr><Nm>Ultimate Creditor</Nm></UltmtCdtr>
<InstrForCdtrAgt><Cd>HOLD</Cd></InstrForCdtrAgt>
<InstrForDbtrAgt>Call first</InstrForDbtrAgt><Purp><Cd>GDDS</Cd></Purp>
<RgltryRptg><DbtCdtRptgInd>CRED</DbtCdtRptgInd><Dtls><Ctry>NL</Ctry>
<Tp><Cd>TYPE1</Cd></Tp><Inf>INFO</Inf></Dtls></RgltryRptg>
<RmtInf><Strd><CdtrRefInf><Tp><CdOrPrtry><Cd>SCOR</Cd></CdOrPrtry></Tp>
<Ref>RF18539007547034</Ref></CdtrRefInf></Strd></RmtInf>
</CdtTrfTxInf>
<CdtTrfTxInf><PmtId><EndToEndId>E2E2</EndToEndId></PmtId>
<Amt><InstdAmt Ccy="EUR">20.00</InstdAmt></Amt>
<ChqInstr><ChqTp>BCHQ</ChqTp></ChqInstr>
<CdtrAgt><FinInstnId><BIC>RABONL2U</BIC><ClrSysMmbId><ClrSysId>
<Prtry>NLCLR</Prtry></ClrSysId><MmbId>99</MmbId></ClrSysMmbId>
</FinInstnId></CdtrAgt>
<Cdtr><Nm>Second Creditor</Nm><Id><OrgId><BICOrBEI>RABONL2U</BICOrBEI>
<Othr><Id>ORG2</Id><SchmeNm><Prtry>PROP</Prtry></SchmeNm></Othr>
</OrgId></Id></Cdtr><Purp><Prtry>PURPX</Prtry></Purp>
<RgltryRptg><Dtls><RptgCd>RCD</RptgCd></Dtls></RgltryRptg>
<RmtInf><Ustrd>Invoice 7</Ustrd></RmtInf>
</CdtTrfTxInf></PmtInf>
</CstmrCdtTrfInitn></Document>"""

DIRECT_DEBIT = f"""<Document xmlns="{DD_NS}"><CstmrDrctDbtInitn>
<GrpHdr><MsgId>DD1</MsgId><NbOfTxs>1</NbOfTxs></GrpHdr>
<PmtInf><PmtInfId>DDP1</PmtInfId><PmtMtd>DD</PmtMtd>
<PmtTpInf><SeqTp>RCUR</SeqTp></PmtTpInf>
<ReqdColltnDt>2026-02-01</ReqdColltnDt>
<Cdtr><Nm>Utility SA</Nm><PstlAdr><Ctry>FR</Ctry></PstlAdr></Cdtr>
<CdtrAcct><Id><IBAN>FR1420041010050500013M02606</IBAN></Id></CdtrAcct>
<CdtrAgt><FinInstnId><BICFI>BNPAFRPPXXX</BICFI></FinInstnId></CdtrAgt>
<UltmtCdtr><Nm>Utility Group</Nm></UltmtCdtr>
<CdtrSchmeId><Id><OrgId><Othr><Id>FR72ZZZ123456</Id></Othr></OrgId></Id>
</CdtrSchmeId>
<DrctDbtTxInf><PmtId><EndToEndId>DDE1</EndToEndId></PmtId>
<InstdAmt Ccy="EUR">42.50</InstdAmt>
<DrctDbtTx><MndtRltdInf><MndtId>MAND-1</MndtId>
<DtOfSgntr>2025-12-01</DtOfSgntr><AmdmntInd>false</AmdmntInd>
</MndtRltdInf><CdtrSchmeId><Id><PrvtId><Othr><Id>FR11ZZZ999999</Id>
</Othr></PrvtId></Id></CdtrSchmeId></DrctDbtTx>
<DbtrAgt><FinInstnId><BICFI>COBADEFFXXX</BICFI></FinInstnId></DbtrAgt>
<Dbtr><Nm>Payer</Nm><Id><PrvtId><Othr><Id>P-9</Id><SchmeNm>
<Prtry>NATID</Prtry></SchmeNm></Othr></PrvtId></Id></Dbtr>
<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>
<UltmtDbtr><Nm>Payer Household</Nm></UltmtDbtr>
</DrctDbtTxInf>
<DrctDbtTxInf><PmtId><EndToEndId>DDE2</EndToEndId></PmtId>
<InstdAmt Ccy="EUR">1.00</InstdAmt></DrctDbtTxInf>
</PmtInf></CstmrDrctDbtInitn></Document>"""

#: What the credit transfer's payment block gives both its transactions.
CT_BLOCK = {
    "id": "MSG1",
    "date": "2026-01-02T09:00:00",
    "nb_of_txs": "2",
    "ctrl_sum": "30.00",
    "initiator_name": "Initiator",
    "payment_information_id": "PMT1",
    "payment_method": "TRF",
    "batch_booking": "true",
    "requested_execution_date": "2026-01-03",
    "charge_bearer": "SLEV",
    "instruction_priority": "HIGH",
    "service_level_code": "SEPA",
    "local_instrument_code": "INST",
    "category_purpose_code": "SUPP",
    "sequence_type": "OOFF",
    "debtor_name": "Debtor Ltd",
    "debtor_town": "Berlin",
    "debtor_country": "DE",
    "debtor_post_code": "10115",
    "debtor_street_name": "Main Street",
    "debtor_address_lines": "Line 1|Line 2",
    "debtor_lei": "5493001KJTIIGC8Y1R12",
    "debtor_other_id": "ORG1",
    "debtor_other_id_scheme": "CUST",
    "debtor_country_of_residence": "AT",
    "debtor_account_IBAN": "DE89370400440532013000",
    "debtor_account_currency": "EUR",
    "debtor_account_type": "OWN",
    "debtor_account_proxy_type": "ALIAS",
    "debtor_account_proxy_id": "debtor@example.org",
    "debtor_agent_BIC": "COBADEFFXXX",
    "debtor_agent_clearing_system": "DEBLZ",
    "debtor_agent_member_id": "37040044",
    "debtor_agent_lei": "5493001KJTIIGC8Y1R12",
    "debtor_agent_name": "Debtor Bank",
    "debtor_agent_other_id": "DAG",
    "ultimate_debtor_name": "Ultimate Debtor",
}

#: The first transaction's own values, primary spellings throughout.
CT_FIRST = {
    "payment_id": "E2E1",
    "end_to_end_id": "E2E1",
    "instruction_id": "INS1",
    "uetr": "8a562c67-ca16-48ba-b074-65581be6f001",
    "charge_bearer": "SHAR",
    "purpose_code": "GDDS",
    "instruction_for_creditor_agent": "HOLD",
    "instruction_for_debtor_agent": "Call first",
    "service_level_proprietary": "TXSVC",
    "payment_amount": "10.00",
    "payment_currency": "EUR",
    "currency": "EUR",
    "creditor_reference": "RF18539007547034",
    "creditor_reference_type": "SCOR",
    "regulatory_reporting_indicator": "CRED",
    "regulatory_reporting_code": "TYPE1",
    "regulatory_reporting_info": "INFO",
    "regulatory_reporting_country": "NL",
    "creditor_name": "Creditor BV",
    "creditor_town": "Amsterdam",
    "creditor_country": "NL",
    "creditor_bic": "INGBNL2A",
    "creditor_account_id": "ACC2",
    "creditor_account_id_scheme": "LOCAL",
    "creditor_account_type": "CACC",
    "creditor_agent_BIC": "INGBNL2AXXX",
    "ultimate_creditor_name": "Ultimate Creditor",
    "intermediary_agent_1_BIC": "DEUTDEFFXXX",
    "intermediary_agent_2_BIC": "BNPAFRPPXXX",
    "intermediary_agent_3_BIC": "NWBKGB2LXXX",
}

#: The second transaction: the alternative spellings.
CT_SECOND = {
    "payment_id": "E2E2",
    "end_to_end_id": "E2E2",
    "purpose_proprietary": "PURPX",
    "cheque_type": "BCHQ",
    "payment_amount": "20.00",
    "payment_currency": "EUR",
    "currency": "EUR",
    "remittance_information": "Invoice 7",
    "regulatory_reporting_code": "RCD",
    "creditor_name": "Second Creditor",
    "creditor_bic": "RABONL2U",
    "creditor_other_id": "ORG2",
    "creditor_other_id_scheme": "PROP",
    "creditor_agent_BIC": "RABONL2U",
    "creditor_agent_clearing_system": "NLCLR",
    "creditor_agent_member_id": "99",
}

#: The direct debit's block: the creditor side and its scheme id.
DD_BLOCK = {
    "id": "DD1",
    "nb_of_txs": "1",
    "payment_information_id": "DDP1",
    "payment_method": "DD",
    "requested_execution_date": "2026-02-01",
    "sequence_type": "RCUR",
    "creditor_name": "Utility SA",
    "creditor_country": "FR",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "creditor_agent_BIC": "BNPAFRPPXXX",
    "ultimate_creditor_name": "Utility Group",
    "creditor_id": "FR72ZZZ123456",
}

#: The first debit: debtor side, mandate, its own scheme id.
DD_FIRST = {
    "creditor_id": "FR11ZZZ999999",
    "payment_id": "DDE1",
    "end_to_end_id": "DDE1",
    "payment_amount": "42.50",
    "payment_currency": "EUR",
    "currency": "EUR",
    "debtor_name": "Payer",
    "debtor_other_id": "P-9",
    "debtor_other_id_scheme": "NATID",
    "debtor_account_IBAN": "DE89370400440532013000",
    "debtor_agent_BIC": "COBADEFFXXX",
    "ultimate_debtor_name": "Payer Household",
    "mandate_id": "MAND-1",
    "date_of_signature": "2025-12-01",
    "amendment_indicator": "false",
}


def test_credit_transfer_rows_carry_every_field() -> None:
    """Both transactions project exactly, the block merged under each."""
    rows = rows_from_xml(CREDIT_TRANSFER)
    assert rows == [CT_BLOCK | CT_FIRST, CT_BLOCK | CT_SECOND]


def test_transaction_values_win_over_the_block() -> None:
    """A transaction's charge bearer replaces the block's; absent keeps it."""
    first, second = rows_from_xml(CREDIT_TRANSFER)
    assert first["charge_bearer"] == "SHAR"
    assert second["charge_bearer"] == "SLEV"


def test_direct_debit_rows_carry_every_field() -> None:
    """The creditor comes from the block, debtor and mandate from the debit."""
    second = {
        "payment_id": "DDE2",
        "end_to_end_id": "DDE2",
        "payment_amount": "1.00",
        "payment_currency": "EUR",
        "currency": "EUR",
    }
    assert rows_from_xml(DIRECT_DEBIT) == [
        DD_BLOCK | DD_FIRST,
        DD_BLOCK | second,
    ]


#: The older spellings and edge forms, laid out with indentation.
OLDER = f"""<Document xmlns="{CT_NS}">
  <CstmrCdtTrfInitn>
    <PmtInf>
      <ReqdExctnDt>2026-03-04</ReqdExctnDt>
      <UltmtDbtr><Nm>Block Ultimate</Nm></UltmtDbtr>
      <CdtTrfTxInf>
        <Amt><EqvtAmt><Amt>7.00</Amt></EqvtAmt></Amt>
        <Cdtr>
          <Id><PrvtId><Othr><Id>P-1</Id>
            <SchmeNm><Cd>NIDN</Cd></SchmeNm></Othr></PrvtId></Id>
        </Cdtr>
        <UltmtDbtr><Nm>Transaction Ultimate</Nm></UltmtDbtr>
        <RmtInf>
          <Strd>
            <CdtrRefInf><Ref>R-1</Ref></CdtrRefInf>
          </Strd>
        </RmtInf>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""


def test_older_spellings_and_edge_forms() -> None:
    """A bare execution date, an equivalent amount without currency, a
    private scheme code, a transaction-level ultimate debtor, and a
    remittance block whose only text is layout."""
    assert rows_from_xml(OLDER) == [
        {
            "requested_execution_date": "2026-03-04",
            "ultimate_debtor_name": "Transaction Ultimate",
            "payment_amount": "7.00",
            "equivalent_amount_currency": "",
            "creditor_reference": "R-1",
            "creditor_other_id": "P-1",
            "creditor_other_id_scheme": "NIDN",
        }
    ]


def test_foreign_document_message() -> None:
    """A document of neither family is refused with a plain message."""
    with pytest.raises(ValueError) as caught:
        rows_from_xml("<Document><Other/></Document>")
    assert str(caught.value) == "not a pain.001 or pain.008 document"
