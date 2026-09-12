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

"""The MDR cross-element rules, each proven to fire and to stay quiet."""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.corpus.rules import mdr

NS1 = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
NS8 = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"


def cct(pmtinf: str = "", tx: str = "", method: str = "TRF") -> str:
    """A minimal pain.001 body with extra content on PmtInf and the transaction."""
    return f"""<Document xmlns="{NS1}"><CstmrCdtTrfInitn><GrpHdr><MsgId>1</MsgId></GrpHdr>
<PmtInf><PmtInfId>P</PmtInfId><PmtMtd>{method}</PmtMtd>
<DbtrAgt><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></DbtrAgt>{pmtinf}
<CdtTrfTxInf><PmtId><EndToEndId>E</EndToEndId></PmtId>{tx}</CdtTrfTxInf>
</PmtInf></CstmrCdtTrfInitn></Document>"""


def dd(pmtinf: str = "", tx: str = "") -> str:
    """A minimal pain.008 body."""
    return f"""<Document xmlns="{NS8}"><CstmrDrctDbtInitn><GrpHdr><MsgId>1</MsgId></GrpHdr>
<PmtInf><PmtInfId>P</PmtInfId><PmtMtd>DD</PmtMtd>
<CdtrAgt><FinInstnId><BICFI>BANKNL2AXXX</BICFI></FinInstnId></CdtrAgt>{pmtinf}
<DrctDbtTxInf><PmtId><EndToEndId>E</EndToEndId></PmtId>{tx}</DrctDbtTxInf>
</PmtInf></CstmrDrctDbtInitn></Document>"""


def ids(xml: str) -> list[str]:
    return [f.rule_id for f in mdr.evaluate_mdr(xml)]


AGENT = (
    "<CdtrAgt><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></CdtrAgt>"
)
ACCT = "<CdtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></CdtrAcct>"
CDTR = "<Cdtr><Nm>C</Nm></Cdtr>"


def test_catalogue_matches_the_report() -> None:
    """Twenty enforced pain.001 rules, nine pain.008, one guidance rule."""
    assert len(mdr.rules_for("pain.001")) == 20
    assert len(mdr.rules_for("pain.008")) == 9
    guidance = [r for r in mdr.RULES if not r.enforced]
    assert [r.rule_id for r in guidance] == ["SupplementaryDataRule"]
    assert len({r.rule_id for r in mdr.RULES}) == len(mdr.RULES)
    assert all(r.definition.endswith(".") for r in mdr.RULES)


@pytest.mark.parametrize(
    ("block", "rule"),
    [
        (
            "<PmtTpInf><InstrPrty>NORM</InstrPrty></PmtTpInf>",
            "PaymentTypeInformationRule",
        ),
        ("<ChrgBr>SLEV</ChrgBr>", "ChargeBearerRule"),
        ("<UltmtDbtr><Nm>U</Nm></UltmtDbtr>", "UltimateDebtorRule"),
        (
            "<InstrForDbtrAgt>x</InstrForDbtrAgt>",
            "InstructionForDebtorAgentRule",
        ),
    ],
)
def test_pmtinf_or_transaction_never_both(block: str, rule: str) -> None:
    """A block on PmtInf forbids the same block on the transaction."""
    assert ids(cct(pmtinf=block, tx=block + CDTR + ACCT)) == [rule]
    assert ids(cct(pmtinf=block, tx=CDTR + ACCT)) == []
    assert ids(cct(tx=block + CDTR + ACCT)) == []


def test_charges_account_rules() -> None:
    """ChrgsAcctAgt needs ChrgsAcct and must be a branch of DbtrAgt."""
    agent = "<ChrgsAcctAgt><FinInstnId><BICFI>BANKDEFF123</BICFI></FinInstnId></ChrgsAcctAgt>"
    other = "<ChrgsAcctAgt><FinInstnId><BICFI>OTHRGB2LXXX</BICFI></FinInstnId></ChrgsAcctAgt>"
    acct = (
        "<ChrgsAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></ChrgsAcct>"
    )
    assert ids(cct(pmtinf=agent, tx=CDTR + ACCT)) == ["ChargesAccountRule"]
    assert ids(cct(pmtinf=acct + agent, tx=CDTR + ACCT)) == []
    assert ids(cct(pmtinf=acct + other, tx=CDTR + ACCT)) == [
        "ChargesAccountAgentRule"
    ]


def test_cheque_rules() -> None:
    """Every cheque constraint fires on its own and stays quiet otherwise."""
    cheque = "<ChqInstr><ChqTp>DRFT</ChqTp></ChqInstr>"
    assert ids(cct(tx=cheque + CDTR + ACCT)) == ["ChequeInstructionRule"]
    assert ids(cct(method="CHK", tx=cheque + CDTR + ACCT)) == [
        "ChequeAndCreditorAccountRule"
    ]
    # no delivery method: agent forbidden
    assert ids(cct(method="CHK", tx=cheque + AGENT + CDTR)) == [
        "ChequeNoDeliveryAndNoCreditorAgentRule"
    ]
    assert ids(cct(method="CHK", tx=cheque + CDTR)) == []
    # delivery to the final agent: agent required
    to_agent = "<ChqInstr><ChqTp>DRFT</ChqTp><DlvryMtd><Cd>MLFA</Cd></DlvryMtd></ChqInstr>"
    assert ids(cct(method="CHK", tx=to_agent + CDTR)) == [
        "ChequeDeliveryAndCreditorAgentRule"
    ]
    assert ids(cct(method="CHK", tx=to_agent + AGENT + CDTR)) == []
    # any other delivery: agent forbidden
    to_creditor = "<ChqInstr><ChqTp>DRFT</ChqTp><DlvryMtd><Cd>MLCD</Cd></DlvryMtd></ChqInstr>"
    proprietary = "<ChqInstr><ChqTp>DRFT</ChqTp><DlvryMtd><Prtry>Hand</Prtry></DlvryMtd></ChqInstr>"
    for instr in (to_creditor, proprietary):
        assert ids(cct(method="CHK", tx=instr + AGENT + CDTR)) == [
            "ChequeDeliveryAndNoCreditorAgentRule"
        ]
        assert ids(cct(method="CHK", tx=instr + CDTR)) == []
    # account with a cheque
    assert "ChequeAndCreditorAccountRule" in ids(
        cct(method="CHK", tx=to_agent + AGENT + CDTR + ACCT)
    )
    # maturity date needs a draft type
    matured = "<ChqInstr><ChqTp>CCHQ</ChqTp><ChqMtrtyDt>2026-01-02</ChqMtrtyDt></ChqInstr>"
    assert ids(cct(method="CHK", tx=matured + CDTR)) == [
        "ChequeMaturityDateRule"
    ]
    ok = "<ChqInstr><ChqTp>ELDR</ChqTp><ChqMtrtyDt>2026-01-02</ChqMtrtyDt></ChqInstr>"
    assert ids(cct(method="CHK", tx=ok + CDTR)) == []
    # a transfer without creditor needs the account
    assert ids(cct(tx="")) == ["NonChequePaymentMethodRule"]
    assert ids(cct(tx=ACCT)) == [] and ids(cct(tx=CDTR)) == []


def test_instruction_for_creditor_agent_and_intermediaries() -> None:
    """CHQB forbids the account; agents and their accounts come in order."""
    chqb = "<InstrForCdtrAgt><Cd>CHQB</Cd></InstrForCdtrAgt>"
    assert ids(cct(tx=chqb + CDTR + ACCT)) == [
        "InstructionForCreditorAgentRule"
    ]
    assert ids(cct(tx=chqb + CDTR)) == []
    phob = "<InstrForCdtrAgt><Cd>PHOB</Cd></InstrForCdtrAgt>"
    assert ids(cct(tx=phob + CDTR + ACCT)) == []

    def agent(n: int) -> str:
        return (
            f"<IntrmyAgt{n}><FinInstnId><BICFI>BANKDEFFXXX</BICFI>"
            f"</FinInstnId></IntrmyAgt{n}>"
        )

    def acct(n: int) -> str:
        return (
            f"<IntrmyAgt{n}Acct><Id><IBAN>DE89370400440532013000</IBAN></Id>"
            f"</IntrmyAgt{n}Acct>"
        )

    assert ids(cct(tx=acct(1) + CDTR + ACCT)) == [
        "IntermediaryAgent1AccountRule"
    ]
    assert ids(cct(tx=agent(2) + CDTR + ACCT)) == ["IntermediaryAgent2Rule"]
    assert ids(cct(tx=agent(1) + agent(3) + CDTR + ACCT)) == [
        "IntermediaryAgent3Rule"
    ]
    assert ids(cct(tx=agent(1) + agent(2) + acct(3) + CDTR + ACCT)) == [
        "IntermediaryAgent3AccountRule"
    ]
    assert ids(cct(tx=agent(1) + acct(2) + CDTR + ACCT)) == [
        "IntermediaryAgent2AccountRule"
    ]
    everything = agent(1) + acct(1) + agent(2) + acct(2) + agent(3) + acct(3)
    assert ids(cct(tx=everything + CDTR + ACCT)) == []


def test_identification_or_proxy() -> None:
    """A cash account needs Id or Prxy; other *Acct blocks are left alone."""
    no_id = "<CdtrAcct><Ccy>EUR</Ccy></CdtrAcct>"
    assert ids(cct(tx=CDTR + no_id)) == ["IdentificationOrProxyPresenceRule"]
    proxy = "<CdtrAcct><Tp><Cd>CACC</Cd></Tp><Prxy><Id>+4917</Id></Prxy></CdtrAcct>"
    assert ids(cct(tx=CDTR + proxy)) == []
    empty = "<CdtrAcct/>"
    assert ids(cct(tx=CDTR + empty)) == []  # nothing to judge


def test_direct_debit_rules() -> None:
    """Placement, amendment indicator and creditor scheme identification."""
    scheme = "<CdtrSchmeId><Nm>S</Nm></CdtrSchmeId>"
    assert ids(dd(pmtinf=scheme, tx=f"<DrctDbtTx>{scheme}</DrctDbtTx>")) == [
        "CreditorSchemeIdentificationRule"
    ]
    assert (
        ids(dd(pmtinf=scheme)) == []
        and ids(dd(tx=f"<DrctDbtTx>{scheme}</DrctDbtTx>")) == []
    )
    for block, rule in [
        (
            "<PmtTpInf><InstrPrty>NORM</InstrPrty></PmtTpInf>",
            "PaymentTypeInformationRule",
        ),
        ("<ChrgBr>SLEV</ChrgBr>", "ChargeBearerRule"),
        ("<UltmtCdtr><Nm>U</Nm></UltmtCdtr>", "UltimateCreditorRule"),
    ]:
        assert ids(dd(pmtinf=block, tx=block)) == [rule]
    on = "<DrctDbtTx><MndtRltdInf><MndtId>M</MndtId><AmdmntInd>true</AmdmntInd></MndtRltdInf></DrctDbtTx>"
    assert ids(dd(tx=on)) == ["AmendmentIndicatorTrueRule"]
    off = "<DrctDbtTx><MndtRltdInf><MndtId>M</MndtId><AmdmntInd>false</AmdmntInd><AmdmntInfDtls><OrgnlMndtId>O</OrgnlMndtId></AmdmntInfDtls></MndtRltdInf></DrctDbtTx>"
    assert ids(dd(tx=off)) == ["AmendmentIndicatorFalseRule"]
    good = "<DrctDbtTx><MndtRltdInf><MndtId>M</MndtId><AmdmntInd>true</AmdmntInd><AmdmntInfDtls><OrgnlMndtId>O</OrgnlMndtId></AmdmntInfDtls></MndtRltdInf></DrctDbtTx>"
    assert ids(dd(tx=good)) == []
    assert (
        ids(
            dd(
                tx="<DrctDbtTx><MndtRltdInf><MndtId>M</MndtId></MndtRltdInf></DrctDbtTx>"
            )
        )
        == []
    )
    charges = "<ChrgsAcct><Id><IBAN>NL91ABNA0417164300</IBAN></Id></ChrgsAcct><ChrgsAcctAgt><FinInstnId><BICFI>OTHRNL2AXXX</BICFI></FinInstnId></ChrgsAcctAgt>"
    assert ids(dd(pmtinf=charges)) == ["ChargesAccountAgentRule"]


def test_finding_shape_and_bad_document() -> None:
    """Findings carry the path and message; a foreign root raises."""
    finding = mdr.evaluate_mdr(
        cct(
            pmtinf="<ChrgBr>SLEV</ChrgBr>",
            tx="<ChrgBr>SLEV</ChrgBr>" + CDTR + ACCT,
        )
    )[0]
    assert finding.rule_id == "ChargeBearerRule"
    assert (
        finding.path == "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/ChrgBr"
    )
    assert "not allowed" in finding.message
    with pytest.raises(ValueError, match="not a pain.001 or pain.008"):
        mdr.evaluate_mdr("<Document><Other/></Document>")


def test_shipped_corpus_is_mdr_clean() -> None:
    """Every market file and every coverage-set file passes the rules."""
    root = (
        Path(__file__).resolve().parent.parent / "pain001" / "corpus" / "data"
    )
    files = sorted(root.rglob("*.xml"))
    assert len(files) > 100
    assert all(
        mdr.evaluate_mdr(f.read_text(encoding="utf-8")) == [] for f in files
    )
