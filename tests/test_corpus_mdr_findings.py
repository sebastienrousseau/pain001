# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Each MDR finding names the right rule, the right place and says why.

The rule tests in ``test_corpus_mdr.py`` check which constraints fire.
These pin the whole finding: the element path a reader is sent to and
the message in the report's terms, including the values quoted in it.
"""

from __future__ import annotations

import pytest
from defusedxml import ElementTree as defused_et

from pain001.corpus.rules import mdr
from tests.test_corpus_mdr import ACCT, AGENT, CDTR, cct, dd

CT_TX = "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf"
CT_PMT = "/Document/CstmrCdtTrfInitn/PmtInf"
DD_TX = "/Document/CstmrDrctDbtInitn/PmtInf/DrctDbtTxInf"
DD_PMT = "/Document/CstmrDrctDbtInitn/PmtInf"
CHARGES_ACCOUNT = (
    "<ChrgsAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></ChrgsAcct>"
)
NO_CDTR = (
    "NonChequePaymentMethodRule",
    CT_TX,
    "PmtMtd is not CHK and Cdtr is absent, so CdtrAcct must be present",
)
NO_AGENT_WITHOUT_DELIVERY = (
    "ChequeNoDeliveryAndNoCreditorAgentRule",
    f"{CT_TX}/CdtrAgt",
    "PmtMtd is CHK without a DlvryMtd, so CdtrAgt is not allowed",
)


def _findings(xml: str) -> list[tuple[str, str, str]]:
    """The findings of a document as plain triples."""
    return [(f.rule_id, f.path, f.message) for f in mdr.evaluate_mdr(xml)]


def _agent(tag: str, bic: str, spelling: str = "BICFI") -> str:
    """An agent block with one BIC."""
    return (
        f"<{tag}><FinInstnId><{spelling}>{bic}</{spelling}>"
        f"</FinInstnId></{tag}>"
    )


def _delivery(code: str) -> str:
    """A cheque instruction with a delivery-method code."""
    return f"<ChqInstr><DlvryMtd><Cd>{code}</Cd></DlvryMtd></ChqInstr>"


def test_exclusive_block_finding() -> None:
    """The transaction's copy is reported, naming block and level."""
    xml = cct("<ChrgBr>SLEV</ChrgBr>", "<ChrgBr>SHAR</ChrgBr>" + CDTR)
    assert _findings(xml) == [
        (
            "ChargeBearerRule",
            f"{CT_TX}/ChrgBr",
            "ChrgBr is present on PmtInf, so it is not allowed on CdtTrfTxInf",
        )
    ]
    assert _findings(cct("", "<ChrgBr>SHAR</ChrgBr>" + CDTR)) == []


def test_charges_account_findings_quote_both_agents() -> None:
    """A lone, foreign charges agent breaks both charges rules."""
    xml = cct(_agent("ChrgsAcctAgt", "OTHRGB2LXXX"), CDTR)
    assert _findings(xml) == [
        (
            "ChargesAccountRule",
            f"{CT_PMT}/ChrgsAcctAgt",
            "ChrgsAcctAgt is present, so ChrgsAcct must be present",
        ),
        (
            "ChargesAccountAgentRule",
            f"{CT_PMT}/ChrgsAcctAgt",
            "ChrgsAcctAgt (OTHRGB2LXXX) must be a branch of DbtrAgt "
            "(BANKDEFFXXX), not a different agent",
        ),
    ]


def test_direct_debit_charges_agent_is_judged_by_the_creditor_agent() -> None:
    """pain.008 compares the charges agent with CdtrAgt."""
    xml = dd(CHARGES_ACCOUNT + _agent("ChrgsAcctAgt", "OTHRNL2AXXX"))
    assert _findings(xml) == [
        (
            "ChargesAccountAgentRule",
            f"{DD_PMT}/ChrgsAcctAgt",
            "ChrgsAcctAgt (OTHRNL2AXXX) must be a branch of CdtrAgt "
            "(BANKNL2AXXX), not a different agent",
        )
    ]


def test_a_branch_of_the_debtor_agent_is_accepted() -> None:
    """Same eight-character BIC, another branch, the older BIC spelling."""
    branch = _agent("ChrgsAcctAgt", "BANKDEFFABC", "BIC")
    assert _findings(cct(CHARGES_ACCOUNT + branch, CDTR)) == []
    node = mdr._Node(defused_et.fromstring(branch), "/A")
    assert mdr._agent_bic(node) == "BANKDEFFABC"
    assert mdr._agent_bic(None) is None


def test_no_debtor_agent_means_no_branch_finding() -> None:
    """Without a debtor agent there is nothing to compare against."""
    xml = cct(_agent("ChrgsAcctAgt", "OTHRGB2LXXX"), CDTR).replace(
        _agent("DbtrAgt", "BANKDEFFXXX"), ""
    )
    assert [f[0] for f in _findings(xml)] == ["ChargesAccountRule"]


def test_cheque_on_a_transfer_findings() -> None:
    """A cheque on TRF is refused, and so is a TRF without a creditor."""
    xml = cct("", "<ChqInstr><ChqTp>BCHQ</ChqTp></ChqInstr>")
    assert _findings(xml) == [
        (
            "ChequeInstructionRule",
            f"{CT_TX}/ChqInstr",
            "PmtMtd is TRF, so ChqInstr is not allowed",
        ),
        NO_CDTR,
    ]
    assert _findings(cct("", ACCT)) == []
    assert _findings(cct("", CDTR)) == []


def test_cheque_account_and_undelivered_agent_findings() -> None:
    """CHK forbids CdtrAcct, and CdtrAgt when no delivery method is set."""
    assert _findings(cct("", AGENT + ACCT, "CHK")) == [
        (
            "ChequeAndCreditorAccountRule",
            f"{CT_TX}/CdtrAcct",
            "PmtMtd is CHK, so CdtrAcct is not allowed",
        ),
        NO_AGENT_WITHOUT_DELIVERY,
    ]
    assert _findings(cct("", "<ChqInstr/>" + AGENT, "CHK")) == [
        NO_AGENT_WITHOUT_DELIVERY
    ]
    assert _findings(cct("", CDTR, "CHK")) == []


def test_every_delivery_to_the_final_agent_needs_the_agent() -> None:
    """MLFA, CRFA, RGFA and PUFA each require CdtrAgt; with it, all is well."""
    for code in sorted(mdr.CHEQUE_TO_AGENT):
        assert _findings(cct("", _delivery(code), "CHK")) == [
            (
                "ChequeDeliveryAndCreditorAgentRule",
                CT_TX,
                f"DlvryMtd {code} delivers to the final agent, so CdtrAgt "
                "must be present",
            )
        ]
        assert _findings(cct("", _delivery(code) + AGENT, "CHK")) == []
    assert mdr.CHEQUE_TO_AGENT == {"MLFA", "CRFA", "RGFA", "PUFA"}


def test_other_deliveries_forbid_the_agent() -> None:
    """A code outside the four, or a proprietary method, forbids CdtrAgt."""
    assert _findings(cct("", _delivery("MLCD") + AGENT, "CHK")) == [
        (
            "ChequeDeliveryAndNoCreditorAgentRule",
            f"{CT_TX}/CdtrAgt",
            "DlvryMtd MLCD does not deliver to the final agent, so CdtrAgt "
            "is not allowed",
        )
    ]
    proprietary = "<ChqInstr><DlvryMtd><Prtry>X</Prtry></DlvryMtd></ChqInstr>"
    assert _findings(cct("", proprietary + AGENT, "CHK"))[0][2] == (
        "DlvryMtd Prtry does not deliver to the final agent, so CdtrAgt "
        "is not allowed"
    )
    assert _findings(cct("", _delivery("MLCD"), "CHK")) == []


def test_maturity_date_needs_a_draft_type() -> None:
    """Only DRFT and ELDR may carry a maturity date; the type is quoted."""
    for cheque_type, expected in (("BCHQ", 1), ("DRFT", 0), ("ELDR", 0)):
        cheque = (
            f"<ChqInstr><ChqTp>{cheque_type}</ChqTp>"
            "<ChqMtrtyDt>2026-01-01</ChqMtrtyDt></ChqInstr>"
        )
        assert len(_findings(cct("", cheque + CDTR, "CHK"))) == expected
    lone = "<ChqInstr><ChqMtrtyDt>2026-01-01</ChqMtrtyDt></ChqInstr>"
    assert _findings(cct("", lone + CDTR, "CHK")) == [
        (
            "ChequeMaturityDateRule",
            f"{CT_TX}/ChqInstr/ChqMtrtyDt",
            "ChqMtrtyDt is present, so ChqTp must be DRFT or ELDR, not None",
        )
    ]
    assert mdr.MATURITY_CHEQUE_TYPES == {"DRFT", "ELDR"}


def test_chqb_instruction_forbids_the_creditor_account() -> None:
    """CHQB among several instruction codes still forbids CdtrAcct."""
    codes = (
        "<InstrForCdtrAgt><Cd>PHOB</Cd></InstrForCdtrAgt>"
        "<InstrForCdtrAgt><Cd>CHQB</Cd></InstrForCdtrAgt>"
    )
    assert _findings(cct("", codes + ACCT)) == [
        (
            "InstructionForCreditorAgentRule",
            f"{CT_TX}/CdtrAcct",
            "InstrForCdtrAgt/Cd CHQB is present, so CdtrAcct is not allowed",
        )
    ]
    assert _findings(cct("", codes + CDTR)) == []


def test_intermediary_account_and_order_findings() -> None:
    """Each account needs its agent; agent n needs agent n - 1."""
    for n in (1, 2, 3):
        account = (
            f"<IntrmyAgt{n}Acct><Id><IBAN>DE89370400440532013000</IBAN>"
            f"</Id></IntrmyAgt{n}Acct>"
        )
        assert _findings(cct("", account + CDTR)) == [
            (
                f"IntermediaryAgent{n}AccountRule",
                f"{CT_TX}/IntrmyAgt{n}Acct",
                f"IntrmyAgt{n}Acct is present, so IntrmyAgt{n} must be "
                "present",
            )
        ]
    for n in (2, 3):
        agent = _agent(f"IntrmyAgt{n}", "BANKFRPPXXX")
        assert _findings(cct("", agent + CDTR)) == [
            (
                f"IntermediaryAgent{n}Rule",
                f"{CT_TX}/IntrmyAgt{n}",
                f"IntrmyAgt{n} is present, so IntrmyAgt{n - 1} must be "
                "present",
            )
        ]
    chain = "".join(_agent(f"IntrmyAgt{n}", "BANKFRPPXXX") for n in (1, 2, 3))
    assert _findings(cct("", chain + CDTR)) == []


def test_amendment_indicator_findings() -> None:
    """True needs the details, false forbids them; each path is exact."""
    details = "<AmdmntInfDtls><OrgnlMndtId>O</OrgnlMndtId></AmdmntInfDtls>"

    def mandate(flag: str, extra: str = "") -> str:
        """A debit carrying a mandate with the given amendment flag."""
        return dd(
            "",
            "<DrctDbtTx><MndtRltdInf><MndtId>M</MndtId>"
            f"<AmdmntInd>{flag}</AmdmntInd>{extra}</MndtRltdInf></DrctDbtTx>",
        )

    assert _findings(mandate("true")) == [
        (
            "AmendmentIndicatorTrueRule",
            f"{DD_TX}/DrctDbtTx/MndtRltdInf",
            "AmdmntInd is true, so AmdmntInfDtls must be present",
        )
    ]
    assert _findings(mandate("false", details)) == [
        (
            "AmendmentIndicatorFalseRule",
            f"{DD_TX}/DrctDbtTx/MndtRltdInf/AmdmntInfDtls",
            "AmdmntInd is false, so AmdmntInfDtls is not allowed",
        )
    ]
    assert _findings(mandate("true", details)) == []
    assert _findings(mandate("false")) == []


def test_creditor_scheme_finding() -> None:
    """A scheme id on both levels is reported on the transaction's copy."""
    scheme = (
        "<CdtrSchmeId><Id><PrvtId><Othr><Id>X</Id></Othr></PrvtId></Id>"
        "</CdtrSchmeId>"
    )
    xml = dd(scheme, f"<DrctDbtTx>{scheme}</DrctDbtTx>")
    assert _findings(xml) == [
        (
            "CreditorSchemeIdentificationRule",
            f"{DD_TX}/DrctDbtTx/CdtrSchmeId",
            "CdtrSchmeId is present on PmtInf, so it is not allowed on the "
            "transaction",
        )
    ]
    assert _findings(dd("", f"<DrctDbtTx>{scheme}</DrctDbtTx>")) == []


def test_identification_or_proxy_findings() -> None:
    """A type, a currency or a name marks a cash account needing Id or Prxy."""
    debtor = "<DbtrAcct><Tp><Cd>CACC</Cd></Tp></DbtrAcct>"
    charges = "<ChrgsAcct><Nm>N</Nm></ChrgsAcct>"
    xml = cct(debtor + charges, "<CdtrAcct><Ccy>EUR</Ccy></CdtrAcct>" + CDTR)
    message = "a cash account must carry Id or Prxy"
    assert _findings(xml) == [
        ("IdentificationOrProxyPresenceRule", f"{CT_PMT}/DbtrAcct", message),
        ("IdentificationOrProxyPresenceRule", f"{CT_PMT}/ChrgsAcct", message),
        ("IdentificationOrProxyPresenceRule", f"{CT_TX}/CdtrAcct", message),
    ]
    proxy = "<CdtrAcct><Ccy>EUR</Ccy><Prxy><Id>+4917</Id></Prxy></CdtrAcct>"
    assert _findings(cct("", proxy + CDTR)) == []
    assert _findings(cct("", "<CdtrAcct/>" + CDTR)) == []


def test_accepted_accounts_do_not_stop_the_search() -> None:
    """A good account and a non-account block before a bad one are passed."""
    good = "<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>"
    xml = cct(
        good + "<ChrgsAcct/>", "<CdtrAcct><Ccy>EUR</Ccy></CdtrAcct>" + CDTR
    )
    assert _findings(xml) == [
        (
            "IdentificationOrProxyPresenceRule",
            f"{CT_TX}/CdtrAcct",
            "a cash account must carry Id or Prxy",
        )
    ]


def test_a_debit_without_mandate_does_not_stop_the_check() -> None:
    """The amendment check moves on past a debit with no mandate."""
    flagged = (
        "<DrctDbtTx><MndtRltdInf><MndtId>M</MndtId>"
        "<AmdmntInd>true</AmdmntInd></MndtRltdInf></DrctDbtTx>"
    )
    second = (
        "</DrctDbtTxInf><DrctDbtTxInf><PmtId><EndToEndId>F</EndToEndId>"
        f"</PmtId>{flagged}"
    )
    assert [f[0] for f in _findings(dd("", second))] == [
        "AmendmentIndicatorTrueRule"
    ]


def test_check_factories_build_working_checks() -> None:
    """A freshly made exclusive or charges-agent check judges a block."""
    xml = cct(
        "<ChrgBr>SLEV</ChrgBr>" + _agent("ChrgsAcctAgt", "OTHRGB2LXXX"),
        "<ChrgBr>SHAR</ChrgBr>" + CDTR,
    )
    body = mdr._Node(defused_et.fromstring(xml), "/Document").get(
        "CstmrCdtTrfInitn", "PmtInf"
    )
    assert body is not None
    exclusive = mdr._exclusive("ChrgBr", "CdtTrfTxInf", "ChargeBearerRule")
    assert exclusive(body) == [
        mdr.MdrFinding(
            "ChargeBearerRule",
            f"{CT_TX}/ChrgBr",
            "ChrgBr is present on PmtInf, so it is not allowed on CdtTrfTxInf",
        )
    ]
    assert mdr._exclusive("UltmtDbtr", "CdtTrfTxInf", "R")(body) == []
    charges = mdr._charges_account_agent("DbtrAgt")
    assert charges(body) == [
        mdr.MdrFinding(
            "ChargesAccountAgentRule",
            f"{CT_PMT}/ChrgsAcctAgt",
            "ChrgsAcctAgt (OTHRGB2LXXX) must be a branch of DbtrAgt "
            "(BANKDEFFXXX), not a different agent",
        )
    ]
    assert mdr._charges_account_agent("CdtrAgt")(body) == []
    plain = cct(_agent("ChrgsAcctAgt", "BANKDEFFABC"), CDTR)
    block = mdr._Node(defused_et.fromstring(plain), "/Document").get(
        "CstmrCdtTrfInitn", "PmtInf"
    )
    assert block is not None and charges(block) == []


def test_foreign_document_message() -> None:
    """A document of neither family is refused with a plain message."""
    with pytest.raises(ValueError) as caught:
        mdr.evaluate_mdr("<Document><Other/></Document>")
    assert str(caught.value) == "not a pain.001 or pain.008 document"


def test_walk_yields_every_descendant_with_its_path() -> None:
    """Depth first, each node with its slash-joined local-name path."""
    root = defused_et.fromstring('<a xmlns="urn:x"><b><c/></b><d>t</d></a>')
    walked = [n.path for n in mdr._Node(root, "/a").walk()]
    assert walked == ["/a/b", "/a/b/c", "/a/d"]
