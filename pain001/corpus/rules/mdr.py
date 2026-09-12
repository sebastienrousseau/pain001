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

"""The ISO 20022 MDR cross-element rules for pain.001 and pain.008.

The Message Definition Report (Payments Initiation, maintenance
2020-2021, part 2) names the constraints an XSD cannot express: a
block allowed at the payment-information level or the transaction
level but not both, the cheque path's dependencies, intermediary
agents in order, charges accounts with their agent. This module
carries every constraint the report defines for the two initiation
messages, quoted from the report, and checks a document against them.

The guidance-level ``SupplementaryDataRule`` is listed for
completeness but not enforced, since the report itself phrases it as
"should".
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from defusedxml import ElementTree as defused_et

CHEQUE_TO_AGENT = frozenset({"MLFA", "CRFA", "RGFA", "PUFA"})
MATURITY_CHEQUE_TYPES = frozenset({"DRFT", "ELDR"})


@dataclass(frozen=True)
class MdrFinding:
    """One violated constraint at one place.

    Attributes:
        rule_id: The MDR constraint name.
        path: The element path the finding sits on.
        message: What went wrong, in the report's terms.
    """

    rule_id: str
    path: str
    message: str


@dataclass(frozen=True)
class MdrRule:
    """One MDR constraint.

    Attributes:
        rule_id: The constraint name in the report.
        messages: The message families it applies to.
        definition: The report's wording.
        enforced: False for guidance the report phrases as "should".
    """

    rule_id: str
    messages: tuple[str, ...]
    definition: str
    enforced: bool = True


def _local(tag: Any) -> str:
    """The local name of a tag, namespace stripped."""
    return str(tag).rsplit("}", 1)[-1]


class _Node:
    """A thin view over an element with path-aware child access."""

    def __init__(self, element: Any, path: str) -> None:
        self.element = element
        self.path = path

    def child(self, name: str) -> _Node | None:
        """The first direct child with local name ``name``."""
        for item in self.element:
            if _local(item.tag) == name:
                return _Node(item, f"{self.path}/{name}")
        return None

    def children(self, name: str) -> list[_Node]:
        """Every direct child with local name ``name``, in order."""
        return [
            _Node(item, f"{self.path}/{name}")
            for item in self.element
            if _local(item.tag) == name
        ]

    def get(self, *names: str) -> _Node | None:
        """Descend through ``names``; ``None`` as soon as one is absent."""
        node: _Node | None = self
        for name in names:
            node = node.child(name) if node is not None else None
        return node

    def text(self, *names: str) -> str | None:
        """The stripped text at the end of ``names``, if present."""
        node = self.get(*names)
        if node is None or node.element.text is None:
            return None
        return str(node.element.text).strip()

    def walk(self) -> Iterator[_Node]:
        """Every descendant, depth first."""
        for item in self.element:
            node = _Node(item, f"{self.path}/{_local(item.tag)}")
            yield node
            yield from node.walk()

    def has(self, *names: str) -> bool:
        """True when the path exists."""
        return self.get(*names) is not None


def _agent_bic(agent: _Node | None) -> str | None:
    """The BIC or BICFI of an agent, whichever the edition spells."""
    if agent is None:
        return None
    return agent.text("FinInstnId", "BICFI") or agent.text("FinInstnId", "BIC")


# --- shared checks ------------------------------------------------------------


def _exclusive(
    block: str, tx_name: str, rule_id: str
) -> Callable[[_Node], list[MdrFinding]]:
    """A block may sit on PmtInf or on each transaction, never both."""

    def check(pmt: _Node) -> list[MdrFinding]:
        """Findings for one PmtInf."""
        if not pmt.has(block):
            return []
        return [
            MdrFinding(
                rule_id,
                tx.path + "/" + block,
                f"{block} is present on PmtInf, so it is not allowed on "
                f"{tx_name}",
            )
            for tx in pmt.children(tx_name)
            if tx.has(block)
        ]

    return check


def _charges_account(pmt: _Node) -> list[MdrFinding]:
    """ChargesAccountRule: ChrgsAcctAgt needs ChrgsAcct."""
    if pmt.has("ChrgsAcctAgt") and not pmt.has("ChrgsAcct"):
        return [
            MdrFinding(
                "ChargesAccountRule",
                pmt.path + "/ChrgsAcctAgt",
                "ChrgsAcctAgt is present, so ChrgsAcct must be present",
            )
        ]
    return []


def _charges_account_agent(
    debtor_side: str,
) -> Callable[[_Node], list[MdrFinding]]:
    """ChrgsAcctAgt must be a branch of the debtor (or creditor) agent."""

    def check(pmt: _Node) -> list[MdrFinding]:
        """Findings for one PmtInf."""
        charges = _agent_bic(pmt.child("ChrgsAcctAgt"))
        main = _agent_bic(pmt.child(debtor_side))
        if charges and main and charges[:8] != main[:8]:
            return [
                MdrFinding(
                    "ChargesAccountAgentRule",
                    pmt.path + "/ChrgsAcctAgt",
                    f"ChrgsAcctAgt ({charges}) must be a branch of "
                    f"{debtor_side} ({main}), not a different agent",
                )
            ]
        return []

    return check


def _identification_or_proxy(root: _Node) -> list[MdrFinding]:
    """Every cash account carries Id or Prxy (editions that allow either)."""
    findings = []
    for node in root.walk():
        name = _local(node.element.tag)
        if not name.endswith("Acct"):
            continue
        if node.has("Id") or node.has("Prxy"):
            continue
        if (
            node.child("Tp") is None
            and node.child("Ccy") is None
            and node.child("Nm") is None
        ):
            continue  # not a cash account block
        findings.append(
            MdrFinding(
                "IdentificationOrProxyPresenceRule",
                node.path,
                "a cash account must carry Id or Prxy",
            )
        )
    return findings


# --- pain.001 --------------------------------------------------------------


def _cheque_rules(pmt: _Node) -> list[MdrFinding]:
    """The seven cheque constraints plus NonChequePaymentMethodRule."""
    method = pmt.text("PmtMtd")
    findings: list[MdrFinding] = []
    for tx in pmt.children("CdtTrfTxInf"):
        cheque = tx.child("ChqInstr")
        if method != "CHK":
            if cheque is not None:
                findings.append(
                    MdrFinding(
                        "ChequeInstructionRule",
                        cheque.path,
                        f"PmtMtd is {method}, so ChqInstr is not allowed",
                    )
                )
            if not tx.has("Cdtr") and not tx.has("CdtrAcct"):
                findings.append(
                    MdrFinding(
                        "NonChequePaymentMethodRule",
                        tx.path,
                        "PmtMtd is not CHK and Cdtr is absent, so CdtrAcct "
                        "must be present",
                    )
                )
        else:
            if tx.has("CdtrAcct"):
                findings.append(
                    MdrFinding(
                        "ChequeAndCreditorAccountRule",
                        tx.path + "/CdtrAcct",
                        "PmtMtd is CHK, so CdtrAcct is not allowed",
                    )
                )
            delivery = cheque.child("DlvryMtd") if cheque is not None else None
            code = delivery.text("Cd") if delivery is not None else None
            agent = tx.has("CdtrAgt")
            if delivery is None and agent:
                findings.append(
                    MdrFinding(
                        "ChequeNoDeliveryAndNoCreditorAgentRule",
                        tx.path + "/CdtrAgt",
                        "PmtMtd is CHK without a DlvryMtd, so CdtrAgt is not allowed",
                    )
                )
            elif (
                delivery is not None and code in CHEQUE_TO_AGENT and not agent
            ):
                findings.append(
                    MdrFinding(
                        "ChequeDeliveryAndCreditorAgentRule",
                        tx.path,
                        f"DlvryMtd {code} delivers to the final agent, so CdtrAgt "
                        "must be present",
                    )
                )
            elif (
                delivery is not None and code not in CHEQUE_TO_AGENT and agent
            ):
                findings.append(
                    MdrFinding(
                        "ChequeDeliveryAndNoCreditorAgentRule",
                        tx.path + "/CdtrAgt",
                        f"DlvryMtd {code or 'Prtry'} does not deliver to the final "
                        "agent, so CdtrAgt is not allowed",
                    )
                )
        if cheque is not None and cheque.has("ChqMtrtyDt"):
            cheque_type = cheque.text("ChqTp")
            if cheque_type not in MATURITY_CHEQUE_TYPES:
                findings.append(
                    MdrFinding(
                        "ChequeMaturityDateRule",
                        cheque.path + "/ChqMtrtyDt",
                        f"ChqMtrtyDt is present, so ChqTp must be DRFT or ELDR, "
                        f"not {cheque_type}",
                    )
                )
    return findings


def _instruction_for_creditor_agent(pmt: _Node) -> list[MdrFinding]:
    """InstructionForCreditorAgentRule: CHQB forbids CdtrAcct."""
    findings = []
    for tx in pmt.children("CdtTrfTxInf"):
        codes = {i.text("Cd") for i in tx.children("InstrForCdtrAgt")}
        if "CHQB" in codes and tx.has("CdtrAcct"):
            findings.append(
                MdrFinding(
                    "InstructionForCreditorAgentRule",
                    tx.path + "/CdtrAcct",
                    "InstrForCdtrAgt/Cd CHQB is present, so CdtrAcct is not allowed",
                )
            )
    return findings


def _intermediary_agents(pmt: _Node) -> list[MdrFinding]:
    """The five intermediary-agent ordering constraints."""
    findings = []
    for tx in pmt.children("CdtTrfTxInf"):
        for n in (1, 2, 3):
            if tx.has(f"IntrmyAgt{n}Acct") and not tx.has(f"IntrmyAgt{n}"):
                findings.append(
                    MdrFinding(
                        f"IntermediaryAgent{n}AccountRule",
                        f"{tx.path}/IntrmyAgt{n}Acct",
                        f"IntrmyAgt{n}Acct is present, so IntrmyAgt{n} must be present",
                    )
                )
        for n in (2, 3):
            if tx.has(f"IntrmyAgt{n}") and not tx.has(f"IntrmyAgt{n - 1}"):
                findings.append(
                    MdrFinding(
                        f"IntermediaryAgent{n}Rule",
                        f"{tx.path}/IntrmyAgt{n}",
                        f"IntrmyAgt{n} is present, so IntrmyAgt{n - 1} must be present",
                    )
                )
    return findings


# --- pain.008 --------------------------------------------------------------


def _amendment_indicator(pmt: _Node) -> list[MdrFinding]:
    """AmendmentIndicatorTrueRule and AmendmentIndicatorFalseRule."""
    findings = []
    for tx in pmt.children("DrctDbtTxInf"):
        mandate = tx.get("DrctDbtTx", "MndtRltdInf")
        if mandate is None:
            continue
        flag = mandate.text("AmdmntInd")
        details = mandate.has("AmdmntInfDtls")
        if flag == "true" and not details:
            findings.append(
                MdrFinding(
                    "AmendmentIndicatorTrueRule",
                    mandate.path,
                    "AmdmntInd is true, so AmdmntInfDtls must be present",
                )
            )
        if flag == "false" and details:
            findings.append(
                MdrFinding(
                    "AmendmentIndicatorFalseRule",
                    mandate.path + "/AmdmntInfDtls",
                    "AmdmntInd is false, so AmdmntInfDtls is not allowed",
                )
            )
    return findings


def _creditor_scheme(pmt: _Node) -> list[MdrFinding]:
    """CreditorSchemeIdentificationRule: PmtInf or transaction, not both."""
    if not pmt.has("CdtrSchmeId"):
        return []
    return [
        MdrFinding(
            "CreditorSchemeIdentificationRule",
            tx.path + "/DrctDbtTx/CdtrSchmeId",
            "CdtrSchmeId is present on PmtInf, so it is not allowed on the "
            "transaction",
        )
        for tx in pmt.children("DrctDbtTxInf")
        if tx.has("DrctDbtTx", "CdtrSchmeId")
    ]


_PAIN001_CHECKS: list[Callable[[_Node], list[MdrFinding]]] = [
    _exclusive("PmtTpInf", "CdtTrfTxInf", "PaymentTypeInformationRule"),
    _exclusive("ChrgBr", "CdtTrfTxInf", "ChargeBearerRule"),
    _exclusive("UltmtDbtr", "CdtTrfTxInf", "UltimateDebtorRule"),
    _exclusive(
        "InstrForDbtrAgt", "CdtTrfTxInf", "InstructionForDebtorAgentRule"
    ),
    _charges_account,
    _charges_account_agent("DbtrAgt"),
    _cheque_rules,
    _instruction_for_creditor_agent,
    _intermediary_agents,
]
_PAIN008_CHECKS: list[Callable[[_Node], list[MdrFinding]]] = [
    _exclusive("PmtTpInf", "DrctDbtTxInf", "PaymentTypeInformationRule"),
    _exclusive("ChrgBr", "DrctDbtTxInf", "ChargeBearerRule"),
    _exclusive("UltmtCdtr", "DrctDbtTxInf", "UltimateCreditorRule"),
    _charges_account,
    _charges_account_agent("CdtrAgt"),
    _amendment_indicator,
    _creditor_scheme,
]

RULES: tuple[MdrRule, ...] = (
    MdrRule(
        "PaymentTypeInformationRule",
        ("pain.001", "pain.008"),
        "If PaymentTypeInformation is present, then the transaction's PaymentTypeInformation is not allowed.",
    ),
    MdrRule(
        "ChargeBearerRule",
        ("pain.001", "pain.008"),
        "If ChargeBearer is present, then the transaction's ChargeBearer is not allowed. Both may be absent.",
    ),
    MdrRule(
        "UltimateDebtorRule",
        ("pain.001",),
        "If UltimateDebtor is present, then CreditTransferTransactionInformation/UltimateDebtor is not allowed. Both may be absent.",
    ),
    MdrRule(
        "UltimateCreditorRule",
        ("pain.008",),
        "If UltimateCreditor is present, then DirectDebitTransactionInformation/UltimateCreditor is not allowed. Both may be absent.",
    ),
    MdrRule(
        "InstructionForDebtorAgentRule",
        ("pain.001",),
        "If InstructionForDebtorAgent is present, then CreditTransferTransactionInformation/InstructionForDebtorAgent is not allowed. Both may be absent.",
    ),
    MdrRule(
        "ChargesAccountRule",
        ("pain.001", "pain.008"),
        "If ChargesAccountAgent is present, then ChargesAccount must be present.",
    ),
    MdrRule(
        "ChargesAccountAgentRule",
        ("pain.001", "pain.008"),
        "If ChargesAccountAgent is present, then it must contain a branch of the DebtorAgent (CreditorAgent for pain.008). It must not contain a completely different agent.",
    ),
    MdrRule(
        "ChequeInstructionRule",
        ("pain.001",),
        "If PaymentMethod is different from CHK (Cheque), then CreditTransferTransactionInformation/ChequeInstruction is not allowed.",
    ),
    MdrRule(
        "ChequeAndCreditorAccountRule",
        ("pain.001",),
        "If PaymentMethod is CHK (Cheque), then CreditTransferTransactionInformation/CreditorAccount is not allowed.",
    ),
    MdrRule(
        "ChequeDeliveryAndCreditorAgentRule",
        ("pain.001",),
        "If PaymentMethod is CHK and ChequeInstruction/DeliveryMethod/Code is MLFA, CRFA, RGFA or PUFA, then CreditorAgent must be present.",
    ),
    MdrRule(
        "ChequeDeliveryAndNoCreditorAgentRule",
        ("pain.001",),
        "If PaymentMethod is CHK and ChequeInstruction/DeliveryMethod/Code is present and different from MLFA, CRFA, RGFA or PUFA, then CreditorAgent is not allowed.",
    ),
    MdrRule(
        "ChequeNoDeliveryAndNoCreditorAgentRule",
        ("pain.001",),
        "If PaymentMethod is CHK and ChequeInstruction/DeliveryMethod is not present, then CreditorAgent is not allowed.",
    ),
    MdrRule(
        "ChequeMaturityDateRule",
        ("pain.001",),
        "If ChequeMaturityDate is present, then ChequeType must be present and equal to DRFT or ELDR.",
    ),
    MdrRule(
        "NonChequePaymentMethodRule",
        ("pain.001",),
        "If PaymentMethod is different from CHK and Creditor is not present, then CreditorAccount must be present.",
    ),
    MdrRule(
        "InstructionForCreditorAgentRule",
        ("pain.001",),
        "If InstructionForCreditorAgent/Code contains CHQB, then CreditorAccount is not allowed.",
    ),
    MdrRule(
        "IntermediaryAgent1AccountRule",
        ("pain.001",),
        "If IntermediaryAgent1Account is present, then IntermediaryAgent1 must be present.",
    ),
    MdrRule(
        "IntermediaryAgent2AccountRule",
        ("pain.001",),
        "If IntermediaryAgent2Account is present, then IntermediaryAgent2 must be present.",
    ),
    MdrRule(
        "IntermediaryAgent3AccountRule",
        ("pain.001",),
        "If IntermediaryAgent3Account is present, then IntermediaryAgent3 must be present.",
    ),
    MdrRule(
        "IntermediaryAgent2Rule",
        ("pain.001",),
        "If IntermediaryAgent2 is present, then IntermediaryAgent1 must be present.",
    ),
    MdrRule(
        "IntermediaryAgent3Rule",
        ("pain.001",),
        "If IntermediaryAgent3 is present, then IntermediaryAgent2 must be present.",
    ),
    MdrRule(
        "AmendmentIndicatorTrueRule",
        ("pain.008",),
        "If AmendmentIndicator is true, then AmendmentInformationDetails must be present.",
    ),
    MdrRule(
        "AmendmentIndicatorFalseRule",
        ("pain.008",),
        "If AmendmentIndicator is false, then AmendmentInformationDetails is not allowed.",
    ),
    MdrRule(
        "CreditorSchemeIdentificationRule",
        ("pain.008",),
        "If CreditorSchemeIdentification is present, then DirectDebitTransactionInformation/CreditorSchemeIdentification is not allowed. Both may be absent.",
    ),
    MdrRule(
        "IdentificationOrProxyPresenceRule",
        ("pain.001", "pain.008"),
        "Identification must be present or Proxy must be present. Both may be present.",
    ),
    MdrRule(
        "SupplementaryDataRule",
        ("pain.001", "pain.008"),
        "The SupplementaryData building block at message level must not be used to provide additional information about a transaction; the transaction-level element should be used for that purpose.",
        enforced=False,
    ),
)


def rules_for(message: str) -> tuple[MdrRule, ...]:
    """The enforced rules of a message family (``pain.001`` or ``pain.008``)."""
    return tuple(r for r in RULES if message in r.messages and r.enforced)


def evaluate_mdr(xml: str) -> list[MdrFinding]:
    """Check a document against every enforced MDR constraint.

    Args:
        xml: A pain.001 or pain.008 document.

    Returns:
        The findings, in rule then document order; empty when the
        document satisfies every constraint.

    Raises:
        ValueError: If the document is neither message family.
    """
    root = _Node(defused_et.fromstring(xml), "/Document")
    body = root.child("CstmrCdtTrfInitn") or root.child("CstmrDrctDbtInitn")
    if body is None:
        raise ValueError("not a pain.001 or pain.008 document")
    checks = (
        _PAIN001_CHECKS
        if _local(body.element.tag) == "CstmrCdtTrfInitn"
        else _PAIN008_CHECKS
    )
    findings: list[MdrFinding] = []
    for pmt in body.children("PmtInf"):
        for check in checks:
            findings.extend(check(pmt))
    findings.extend(_identification_or_proxy(body))
    return findings


__all__ = [
    "CHEQUE_TO_AGENT",
    "MATURITY_CHEQUE_TYPES",
    "RULES",
    "MdrFinding",
    "MdrRule",
    "evaluate_mdr",
    "rules_for",
]
