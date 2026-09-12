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

"""Scenario to XML, one edition at a time (ADR-0003, decision 6).

The builder works in four passes:

1. **compose**: the friendly scenario keys become a tree keyed by ISO
   element names (``GrpHdr``, ``PmtInf`` ...), the same tree for every
   edition. ``raw`` objects are merged in verbatim, so anything the
   friendly layer does not name can still be expressed.
2. **conform**: the tree is walked against the target edition's
   :class:`~pain001.corpus.inventory.Inventory`. An element the
   edition spells differently is renamed (``BIC`` and ``BICFI``,
   ``BICOrBEI`` and ``AnyBIC``); a scalar that meets a choice is
   wrapped (``AdrTp`` became ``Cd``/``Prtry`` in .09, ``ReqdExctnDt``
   became ``Dt``/``DtTm``); a wrapped value that meets a plain element
   is unwrapped; a repeat the edition caps is cut to the cap; an
   element the edition does not declare is dropped. Every such move is
   listed in the :class:`BuildReport`.
3. **order**: children are sorted into the schema's declared order,
   read from the inventory, and empty branches pruned.
4. **serialise and validate**: lxml writes the document with a fixed
   indentation and declaration, then the edition's XSD must accept it,
   or :class:`BuildError` carries the reasons.

Values are strings all the way through, so ``425000.00`` renders as
written and a rebuild is byte-identical.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pain001.corpus import identifiers as ids
from pain001.corpus.inventory import ElementEntry, Inventory, inventory_for
from pain001.corpus.registry import Scenario, scenario_from
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.validate_via_xsd import collect_xsd_validation_errors

#: Elements that changed name between editions but not meaning.
ALIASES: dict[str, tuple[str, ...]] = {
    "BIC": ("BICFI",),
    "BICFI": ("BIC",),
    "BICOrBEI": ("AnyBIC",),
    "AnyBIC": ("BICOrBEI",),
}
#: When a scalar meets a complex slot, the child that carries it.
WRAP_PREFERENCE: tuple[str, ...] = ("Cd", "Dt", "DtTm", "Tp", "Id")
ROOTS = {"pain.001": "CstmrCdtTrfInitn", "pain.008": "CstmrDrctDbtInitn"}
#: Markets that write the house number before the street on a line.
NUMBER_FIRST = frozenset({"GB", "US", "HK", "SG", "MY", "IE", "AU", "CA"})
INDENT = "  "

Tree = dict[str, Any]


class BuildError(ValueError):
    """The rendered document did not validate; the message says why."""


@dataclass
class BuildReport:
    """What the conform pass had to do to fit the edition.

    Attributes:
        version: The edition built.
        renamed: ``(path, new_name)`` for each alias applied.
        wrapped: Paths where a scalar was wrapped into a choice child.
        unwrapped: Paths where a wrapped value was flattened.
        dropped: Paths the edition does not declare, left out.
        truncated: Paths where a repeat was cut to the edition's cap.
    """

    version: str
    renamed: list[tuple[str, str]] = field(default_factory=list)
    wrapped: list[str] = field(default_factory=list)
    unwrapped: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BuildResult:
    """A rendered edition and the report of how it was fitted."""

    version: str
    xml: str
    report: BuildReport


# --- compose -----------------------------------------------------------------


def _code(value: Any) -> Tree | None:
    """``"SEPA"`` or ``{code: X}`` / ``{proprietary: X}`` to ``Cd``/``Prtry``."""
    if value is None:
        return None
    if isinstance(value, str):
        return {"Cd": value}
    if "code" in value:
        return {"Cd": value["code"]}
    return {"Prtry": value["proprietary"]}


def _merge(target: Tree, raw: Tree | None) -> Tree:
    """Merge a ``raw`` object into a composed tree, raw winning."""
    if not raw:
        return target
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = _merge(dict(target[key]), value)
        else:
            target[key] = value
    return target


def _drop_none(tree: Tree) -> Tree:
    """The tree without its ``None`` values."""
    return {k: v for k, v in tree.items() if v is not None}


class _Composer:
    """Turns one scenario into the edition-neutral ISO tree."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.data = scenario.data
        self.country = scenario.country
        self._seed = scenario.seed
        self._counter = 0

    def _next_seed(self, key: str | None = None) -> int:
        """A seed for one auto value: stable per ``key``, else sequential."""
        if key is not None:
            return self._seed * 1000 + sum(ord(c) for c in key) % 997
        self._counter += 1
        return self._seed * 1000 + self._counter

    # parties, accounts, agents, addresses

    def party(self, spec: Tree | None) -> Tree | None:
        """A party block: ``Nm``, ``PstlAdr``, ``Id``, ``CtryOfRes``, ``CtctDtls``."""
        if spec is None:
            return None
        key = spec.get("ref")
        if key is not None:
            base = dict(self.data.get("parties", {}).get(key) or {})
            if not base:
                raise BuildError(
                    f"{self.scenario.id}: party ref {key!r} is not "
                    "defined under parties"
                )
            spec = deep_merge(
                base, {k: v for k, v in spec.items() if k != "ref"}
            )
        tree: Tree = {
            "Nm": spec.get("name"),
            "PstlAdr": self.address(spec.get("address")),
            "Id": self.party_id(spec.get("id"), key),
            "CtryOfRes": spec.get("country_of_residence"),
            "CtctDtls": self.contact(spec.get("contact")),
        }
        return _merge(_drop_none(tree), spec.get("raw"))

    def party_id(
        self, spec: Tree | None, key: str | None = None
    ) -> Tree | None:
        """``OrgId`` or ``PrvtId``; ``key`` keeps a ref's auto LEI stable."""
        if spec is None:
            return None
        if "org" in spec:
            org = spec["org"]
            return {
                "OrgId": _drop_none(
                    {
                        "AnyBIC": org.get("bic"),
                        "LEI": self.lei(org.get("lei"), key),
                        "Othr": [
                            self.other_id(o) for o in org.get("other", [])
                        ]
                        or None,
                    }
                )
            }
        prv = spec["private"]
        birth = prv.get("birth")
        return {
            "PrvtId": _drop_none(
                {
                    "DtAndPlcOfBirth": _drop_none(
                        {
                            "BirthDt": birth["date"],
                            "PrvcOfBirth": birth.get("province"),
                            "CityOfBirth": birth["city"],
                            "CtryOfBirth": birth["country"],
                        }
                    )
                    if birth
                    else None,
                    "Othr": [self.other_id(o) for o in prv.get("other", [])]
                    or None,
                }
            )
        }

    def lei(self, value: str | None, key: str | None = None) -> str | None:
        """An LEI as given, or a checked synthetic one for ``auto``."""
        if value == "auto":
            return ids.make_lei(self._next_seed(key))
        return value

    @staticmethod
    def other_id(spec: Tree) -> Tree:
        """``Othr``: ``Id``, ``SchmeNm`` (``Cd`` or ``Prtry``), ``Issr``."""
        scheme = None
        if spec.get("scheme"):
            scheme = {"Cd": spec["scheme"]}
        elif spec.get("proprietary_scheme"):
            scheme = {"Prtry": spec["proprietary_scheme"]}
        return _drop_none(
            {"Id": spec["id"], "SchmeNm": scheme, "Issr": spec.get("issuer")}
        )

    @staticmethod
    def contact(spec: Tree | None) -> Tree | None:
        """``CtctDtls``."""
        if spec is None:
            return None
        tree = _drop_none(
            {
                "NmPrfx": spec.get("prefix"),
                "Nm": spec.get("name"),
                "PhneNb": spec.get("phone"),
                "MobNb": spec.get("mobile"),
                "FaxNb": spec.get("fax"),
                "EmailAdr": spec.get("email"),
            }
        )
        return _merge(tree, spec.get("raw"))

    @staticmethod
    def address(spec: Tree | None) -> Tree | None:
        """``PstlAdr`` in the structured, hybrid or unstructured form."""
        if spec is None:
            return None
        form = spec.get("form", "hybrid")
        structured = {
            "AdrTp": _code(spec.get("type")),
            "Dept": spec.get("department"),
            "SubDept": spec.get("sub_department"),
            "StrtNm": spec.get("street"),
            "BldgNb": spec.get("building_number"),
            "BldgNm": spec.get("building_name"),
            "Flr": spec.get("floor"),
            "PstBx": spec.get("post_box"),
            "Room": spec.get("room"),
            "PstCd": spec.get("post_code"),
            "TwnNm": spec.get("town"),
            "TwnLctnNm": spec.get("town_location"),
            "DstrctNm": spec.get("district"),
            "CtrySubDvsn": spec.get("country_subdivision"),
            "Ctry": spec.get("country"),
        }
        lines = list(spec.get("lines") or [])
        if not lines:
            parts = [spec.get("street"), spec.get("building_number")]
            if spec.get("country") in NUMBER_FIRST:
                parts.reverse()
            street = " ".join(p for p in parts if p)
            if street:
                lines.append(street)
            town = " ".join(
                p for p in (spec.get("post_code"), spec.get("town")) if p
            )
            if town and form == "unstructured":
                lines.append(town)
        if form == "structured":
            tree = dict(structured)
        elif form == "unstructured":
            tree = {"Ctry": spec.get("country"), "AdrLine": lines or None}
        else:  # hybrid: town and country structured, the street on a line
            tree = {
                "Dept": structured["Dept"],
                "SubDept": structured["SubDept"],
                "PstCd": structured["PstCd"],
                "TwnNm": structured["TwnNm"],
                "CtrySubDvsn": structured["CtrySubDvsn"],
                "Ctry": structured["Ctry"],
                "AdrLine": lines[:2] or None,
            }
        return _merge(_drop_none(tree), spec.get("raw"))

    def account(
        self, spec: Tree | None, country: str | None = None
    ) -> Tree | None:
        """``…Acct``: ``Id`` (IBAN or ``Othr``), ``Tp``, ``Ccy``, ``Nm``, ``Prxy``."""
        if spec is None:
            return None
        iban = spec.get("iban")
        if iban == "auto":
            iban = ids.iban_for(country or self.country, self._next_seed())
        identification: Tree
        if iban:
            identification = {"IBAN": iban}
        elif spec.get("other"):
            identification = {"Othr": self.other_id(spec["other"])}
        else:
            raise BuildError(
                f"{self.scenario.id}: an account needs iban or other"
            )
        proxy = spec.get("proxy")
        tree = _drop_none(
            {
                "Id": identification,
                "Tp": _code(spec.get("type")),
                "Ccy": spec.get("currency"),
                "Nm": spec.get("name"),
                "Prxy": _drop_none(
                    {"Tp": _code(proxy.get("type")), "Id": proxy["id"]}
                )
                if proxy
                else None,
            }
        )
        return _merge(tree, spec.get("raw"))

    def agent(self, spec: Tree | None) -> Tree | None:
        """``…Agt``: ``FinInstnId`` and ``BrnchId``."""
        if spec is None:
            return None
        bic = spec.get("bic")
        if bic == "auto":
            bic = ids.make_bic(
                spec.get("country", self.country), self._next_seed()
            )
        clearing = spec.get("clearing")
        fin = _drop_none(
            {
                "BICFI": bic,
                "ClrSysMmbId": _drop_none(
                    {
                        "ClrSysId": _code(clearing.get("system")),
                        "MmbId": clearing["member_id"],
                    }
                )
                if clearing
                else None,
                "LEI": self.lei(spec.get("lei")),
                "Nm": spec.get("name"),
                "PstlAdr": self.address(spec.get("address")),
                "Othr": self.other_id(spec["other"])
                if spec.get("other")
                else None,
            }
        )
        branch = spec.get("branch")
        tree = _drop_none(
            {
                "FinInstnId": fin,
                "BrnchId": _drop_none(
                    {
                        "Id": branch.get("id"),
                        "LEI": self.lei(branch.get("lei")),
                        "Nm": branch.get("name"),
                        "PstlAdr": self.address(branch.get("address")),
                    }
                )
                if branch
                else None,
            }
        )
        return _merge(tree, spec.get("raw"))

    # blocks

    @staticmethod
    def payment_type(spec: Tree | None) -> Tree | None:
        """``PmtTpInf``."""
        if spec is None:
            return None
        levels = spec.get("service_level")
        if levels is not None and not isinstance(levels, list):
            levels = [levels]
        tree = _drop_none(
            {
                "InstrPrty": spec.get("priority"),
                "SvcLvl": [_code(v) for v in levels] if levels else None,
                "LclInstrm": _code(spec.get("local_instrument")),
                "SeqTp": spec.get("sequence_type"),
                "CtgyPurp": _code(spec.get("category_purpose")),
            }
        )
        return tree or None

    @staticmethod
    def amount(spec: Tree) -> Tree:
        """An amount with its ``Ccy`` attribute."""
        return {"@Ccy": spec["ccy"], "$": spec["value"]}

    def remittance(self, spec: Tree | None) -> Tree | None:
        """``RmtInf`` with ``Ustrd`` lines and ``Strd`` blocks."""
        if spec is None:
            return None
        unstructured = spec.get("unstructured")
        if isinstance(unstructured, str):
            unstructured = [unstructured]
        structured = [
            self.structured_remittance(s) for s in spec.get("structured", [])
        ]
        return _drop_none(
            {"Ustrd": unstructured or None, "Strd": structured or None}
        )

    def structured_remittance(self, spec: Tree) -> Tree:
        """One ``Strd`` block."""
        documents = [
            _drop_none(
                {
                    "Tp": _drop_none(
                        {
                            "CdOrPrtry": _code(d.get("type")),
                            "Issr": d.get("issuer"),
                        }
                    )
                    if d.get("type") or d.get("issuer")
                    else None,
                    "Nb": d.get("number"),
                    "RltdDt": d.get("date"),
                }
            )
            for d in spec.get("documents", [])
        ]
        amounts = spec.get("amounts") or {}
        reference = spec.get("creditor_reference")
        tree = _drop_none(
            {
                "RfrdDocInf": documents or None,
                "RfrdDocAmt": _drop_none(
                    {
                        "DuePyblAmt": self.amount(amounts["due"])
                        if amounts.get("due")
                        else None,
                        "CdtNoteAmt": self.amount(amounts["credit_note"])
                        if amounts.get("credit_note")
                        else None,
                        "RmtdAmt": self.amount(amounts["remitted"])
                        if amounts.get("remitted")
                        else None,
                    }
                )
                or None,
                "CdtrRefInf": _drop_none(
                    {
                        "Tp": _drop_none(
                            {
                                "CdOrPrtry": _code(reference.get("type")),
                                "Issr": reference.get("issuer"),
                            }
                        )
                        if reference.get("type") or reference.get("issuer")
                        else None,
                        "Ref": reference["reference"],
                    }
                )
                if reference
                else None,
                "Invcr": self.party(spec.get("invoicer")),
                "Invcee": self.party(spec.get("invoicee")),
                "AddtlRmtInf": spec.get("additional") or None,
            }
        )
        return _merge(tree, spec.get("raw"))

    def mandate(self, spec: Tree | None) -> Tree | None:
        """``MndtRltdInf``."""
        if spec is None:
            return None
        amendment = spec.get("amendment_indicator")
        tree = _drop_none(
            {
                "MndtId": spec["id"],
                "DtOfSgntr": spec.get("date_of_signature"),
                "AmdmntInd": None
                if amendment is None
                else ("true" if amendment else "false"),
                "ElctrncSgntr": spec.get("electronic_signature"),
                "FrstColltnDt": spec.get("first_collection_date"),
                "FnlColltnDt": spec.get("final_collection_date"),
                "Frqcy": spec.get("frequency"),
            }
        )
        return _merge(tree, spec.get("raw"))

    def transaction(self, spec: Tree, direct_debit: bool) -> Tree:
        """``CdtTrfTxInf`` or ``DrctDbtTxInf``."""
        uetr = spec.get("uetr")
        if uetr == "auto":
            uetr = ids.make_uetr(self._next_seed())
        payment_id = _drop_none(
            {
                "InstrId": spec.get("instruction_id"),
                "EndToEndId": spec["end_to_end_id"],
                "UETR": uetr,
            }
        )
        instructions = [
            _drop_none({"Cd": i.get("code"), "InstrInf": i.get("text")})
            for i in spec.get("instructions_for_creditor_agent", [])
        ]
        agents = spec.get("intermediary_agents", [])
        common: Tree = {
            "PmtId": payment_id,
            "PmtTpInf": self.payment_type(spec.get("type")),
            "ChrgBr": spec.get("charge_bearer"),
            "UltmtDbtr": self.party(spec.get("ultimate_debtor")),
            "UltmtCdtr": self.party(spec.get("ultimate_creditor")),
            "InstrForCdtrAgt": instructions or None,
            "InstrForDbtrAgt": spec.get("instruction_for_debtor_agent"),
            "Purp": _code(spec.get("purpose")),
            "RmtInf": self.remittance(spec.get("remittance")),
        }
        if direct_debit:
            pre = spec.get("pre_notification") or {}
            tree = {
                **common,
                "InstdAmt": self.amount(spec["amount"]),
                "DrctDbtTx": _drop_none(
                    {
                        "MndtRltdInf": self.mandate(spec.get("mandate")),
                        "CdtrSchmeId": self.party(
                            spec.get("creditor_scheme_id")
                        ),
                        "PreNtfctnId": pre.get("id"),
                        "PreNtfctnDt": pre.get("date"),
                    }
                )
                or None,
                "DbtrAgt": self.agent(spec.get("debtor_agent")),
                "DbtrAgtAcct": self.account(spec.get("debtor_agent_account")),
                "Dbtr": self.party(spec.get("debtor")),
                "DbtrAcct": self.account(
                    spec.get("debtor_account"),
                    self._party_country(spec.get("debtor")),
                ),
            }
        else:
            equivalent = spec.get("equivalent_amount")
            rate = spec.get("exchange_rate")
            tree = {
                **common,
                "Amt": {
                    "EqvtAmt": {
                        "Amt": self.amount(equivalent["amount"]),
                        "CcyOfTrf": equivalent["currency_of_transfer"],
                    }
                }
                if equivalent
                else {"InstdAmt": self.amount(spec["amount"])},
                "XchgRateInf": _drop_none(
                    {
                        "UnitCcy": rate.get("unit_currency"),
                        "XchgRate": rate.get("rate"),
                        "RateTp": rate.get("type"),
                        "CtrctId": rate.get("contract_id"),
                    }
                )
                if rate
                else None,
                "IntrmyAgt1": self.agent(agents[0])
                if len(agents) > 0
                else None,
                "IntrmyAgt2": self.agent(agents[1])
                if len(agents) > 1
                else None,
                "IntrmyAgt3": self.agent(agents[2])
                if len(agents) > 2
                else None,
                "CdtrAgt": self.agent(spec.get("creditor_agent")),
                "CdtrAgtAcct": self.account(
                    spec.get("creditor_agent_account")
                ),
                "Cdtr": self.party(spec.get("creditor")),
                "CdtrAcct": self.account(
                    spec.get("creditor_account"),
                    self._party_country(spec.get("creditor")),
                ),
            }
        return _merge(_drop_none(tree), spec.get("raw"))

    def _party_country(self, spec: Tree | None) -> str | None:
        """The country an ``auto`` account should belong to."""
        if not spec:
            return None
        if "ref" in spec:
            spec = {
                **self.data.get("parties", {}).get(spec["ref"], {}),
                **spec,
            }
        address = spec.get("address") or {}
        return address.get("country") or spec.get("country_of_residence")

    def compose(self) -> tuple[str, Tree]:
        """The root element name and the full edition-neutral tree."""
        direct_debit = self.scenario.message == "pain.008"
        header = self.data.get("header", {})
        payment = self.data["payment"]
        transactions = [
            self.transaction(t, direct_debit)
            for t in self.data["transactions"]
        ]
        count = str(len(transactions))
        control = (
            str(
                sum(
                    Decimal(t["amount"]["value"])
                    for t in self.data["transactions"]
                )
            )
            if header.get("control_sum", True)
            else None
        )
        grp = _drop_none(
            {
                "MsgId": header.get("message_id", f"{self.scenario.id}"),
                "CreDtTm": header.get("created", "2026-01-02T09:00:00"),
                "Authstn": [_code(a) for a in header.get("authorisation", [])]
                or None,
                "NbOfTxs": count,
                "CtrlSum": control,
                "InitgPty": self.party(header.get("initiating_party"))
                or {"Nm": "pain001 corpus"},
                "FwdgAgt": self.agent(header.get("forwarding_agent")),
            }
        )
        pmt: Tree = {
            "PmtInfId": payment.get("id", "PMT-1"),
            "PmtMtd": payment.get("method", "DD" if direct_debit else "TRF"),
            "BtchBookg": None
            if payment.get("batch_booking") is None
            else ("true" if payment["batch_booking"] else "false"),
            "NbOfTxs": count,
            "CtrlSum": control,
            "PmtTpInf": self.payment_type(payment.get("type")),
        }
        if direct_debit:
            pmt.update(
                {
                    "ReqdColltnDt": payment.get("requested_collection_date"),
                    "Cdtr": self.party(payment.get("creditor")),
                    "CdtrAcct": self.account(
                        payment.get("creditor_account"),
                        self._party_country(payment.get("creditor")),
                    ),
                    "CdtrAgt": self.agent(payment.get("creditor_agent")),
                    "CdtrAgtAcct": self.account(
                        payment.get("creditor_agent_account")
                    ),
                    "UltmtCdtr": self.party(payment.get("ultimate_creditor")),
                    "ChrgBr": payment.get("charge_bearer"),
                    "ChrgsAcct": self.account(payment.get("charges_account")),
                    "ChrgsAcctAgt": self.agent(
                        payment.get("charges_account_agent")
                    ),
                    "CdtrSchmeId": self.party(
                        payment.get("creditor_scheme_id")
                    ),
                    "DrctDbtTxInf": transactions,
                }
            )
        else:
            pmt.update(
                {
                    "ReqdExctnDt": payment.get("requested_execution_date"),
                    "PoolgAdjstmntDt": payment.get("pooling_adjustment_date"),
                    "Dbtr": self.party(payment.get("debtor")),
                    "DbtrAcct": self.account(
                        payment.get("debtor_account"),
                        self._party_country(payment.get("debtor")),
                    ),
                    "DbtrAgt": self.agent(payment.get("debtor_agent")),
                    "DbtrAgtAcct": self.account(
                        payment.get("debtor_agent_account")
                    ),
                    "UltmtDbtr": self.party(payment.get("ultimate_debtor")),
                    "ChrgBr": payment.get("charge_bearer"),
                    "ChrgsAcct": self.account(payment.get("charges_account")),
                    "ChrgsAcctAgt": self.agent(
                        payment.get("charges_account_agent")
                    ),
                    "CdtTrfTxInf": transactions,
                }
            )
        root = {
            "GrpHdr": _merge(grp, header.get("raw")),
            "PmtInf": _merge(_drop_none(pmt), payment.get("raw")),
        }
        return ROOTS[self.scenario.message], root


# --- conform, order, serialise ------------------------------------------------


class _Fitter:
    """Fits a composed tree to one edition's inventory."""

    def __init__(self, inventory: Inventory, report: BuildReport) -> None:
        self.report = report
        self.children: dict[str, dict[str, ElementEntry]] = {}
        self.any_slots: set[str] = set()
        for entry in inventory.elements:
            parent, name = entry.path.rsplit("/", 1)
            if entry.kind == "attribute":
                continue
            if entry.kind == "any":
                self.any_slots.add(parent)
                continue
            self.children.setdefault(parent, {})[name] = entry

    def tree(self, node: Tree, path: str) -> Tree:
        """Conform and order one complex node."""
        declared = self.children.get(path, {})
        fitted: Tree = {}
        for key, value in node.items():
            name = key
            if name not in declared:
                alias = next(
                    (a for a in ALIASES.get(name, ()) if a in declared), None
                )
                if alias is not None:
                    self.report.renamed.append((f"{path}/{name}", alias))
                    name = alias
                elif path in self.any_slots:
                    fitted[name] = value  # free content under xs:any
                    continue
                else:
                    self.report.dropped.append(f"{path}/{name}")
                    continue
            value = self.value(value, f"{path}/{name}", declared[name])
            if value is not None and value != {} and value != []:
                fitted[name] = value
        ordered = {name: fitted[name] for name in declared if name in fitted}
        for name, value in fitted.items():  # content under an xs:any slot
            if name not in ordered:
                ordered[name] = value
        return ordered

    def value(self, value: Any, path: str, entry: ElementEntry) -> Any:
        """Conform one value to its declared slot."""
        if value is None:
            return None
        if isinstance(value, list):
            items = [self.value(v, path, entry) for v in value]
            items = [i for i in items if i is not None and i != {}]
            if entry.max_occurs is not None and len(items) > entry.max_occurs:
                self.report.truncated.append(path)
                items = items[: entry.max_occurs]
            if entry.max_occurs == 1:
                return items[0] if items else None
            return items
        if entry.kind == "simple":
            if isinstance(value, dict):
                if "$" in value or any(k.startswith("@") for k in value):
                    return {
                        k: v
                        for k, v in value.items()
                        if k == "$" or k.startswith("@")
                    }
                for pick in WRAP_PREFERENCE:
                    if pick in value:
                        self.report.unwrapped.append(path)
                        return self.value(value[pick], path, entry)
                self.report.dropped.append(path)
                return None
            return value
        if not isinstance(value, dict):
            declared = self.children.get(path, {})
            wrap: str | None = None
            if "DtTm" in declared and "Dt" in declared and "T" in str(value):
                wrap = "DtTm"
            else:
                wrap = next(
                    (p for p in WRAP_PREFERENCE if p in declared), None
                )
            if wrap is None:
                self.report.dropped.append(path)
                return None
            self.report.wrapped.append(path)
            return self.tree({wrap: value}, path)
        fitted = self.tree(value, path)
        return fitted or None


def _serialise(root_name: str, tree: Tree, namespace: str) -> str:
    """Write the tree as a pretty-printed, declared UTF-8 document."""
    # The builder is a maintainer tool; twins and the API must not pay for lxml.
    from lxml import etree  # noqa: PLC0415

    document = etree.Element(
        f"{{{namespace}}}Document", nsmap={None: namespace}
    )
    root = etree.SubElement(document, f"{{{namespace}}}{root_name}")
    _fill(root, tree, namespace)
    etree.indent(document, space=INDENT)
    payload = etree.tostring(
        document, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
    return str(payload.decode("utf-8"))


def _text(value: Any) -> str:
    """The XML text of a scalar; booleans as ``true``/``false``."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _fill(element: Any, tree: Tree, namespace: str) -> None:
    """Add ``tree`` under ``element`` as namespaced children."""
    from lxml import etree  # noqa: PLC0415

    for key, value in tree.items():
        if key == "$":
            element.text = _text(value)
        elif key.startswith("@"):
            element.set(key[1:], _text(value))
        else:
            items = value if isinstance(value, list) else [value]
            for item in items:
                child = etree.SubElement(element, f"{{{namespace}}}{key}")
                if isinstance(item, dict):
                    _fill(child, item, namespace)
                else:
                    child.text = _text(item)


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """A copy of ``base`` with ``patch`` merged in, nested dicts recursively.

    Args:
        base: The scenario document.
        patch: Keys to set; a nested dict merges, anything else replaces;
            ``{"*": {...}}`` against a list merges into every item;
            ``None`` removes the key.

    Returns:
        The merged copy; neither input is modified.
    """
    merged = dict(base)
    for key, value in patch.items():
        current = merged.get(key)
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(current, dict):
            merged[key] = deep_merge(current, value)
        elif (
            isinstance(value, dict)
            and isinstance(current, list)
            and "*" in value
        ):
            merged[key] = [
                deep_merge(item, value["*"])
                if isinstance(item, dict)
                else item
                for item in current
            ]
        else:
            merged[key] = value
    return merged


def build(
    scenario: Scenario | dict[str, Any],
    version: str,
    patch: dict[str, Any] | None = None,
) -> BuildResult:
    """Render one scenario in one edition.

    Args:
        scenario: A :class:`Scenario` or a scenario document.
        version: A bundled message type the scenario lists.
        patch: Scenario keys to merge in first, as an overlay's ``patch``
            does for a bank variant.

    Returns:
        The :class:`BuildResult` with XML text and the fit report.

    Raises:
        BuildError: If the scenario cannot be composed, does not list
            the version, or the rendered document fails the XSD.
    """
    if not isinstance(scenario, Scenario):
        scenario = scenario_from(scenario)
    if patch:
        scenario = scenario_from(
            deep_merge(scenario.data, patch), scenario.source
        )
    if version not in scenario.versions:
        raise BuildError(
            f"{scenario.id} does not list {version}; it lists {', '.join(scenario.versions)}"
        )
    root_name, tree = _Composer(scenario).compose()
    inventory = inventory_for(version)
    report = BuildReport(version)
    fitted = _Fitter(inventory, report).tree({root_name: tree}, "/Document")
    xml = _serialise(root_name, fitted[root_name], inventory.namespace)
    xsd = DEFAULT_TEMPLATE_REGISTRY.get_template(version).xsd_path
    errors = collect_xsd_validation_errors(xml, str(xsd), max_errors=5)
    if errors:
        errors = [re.sub(r"\{urn:[^}]+\}", "", e) for e in errors]
        raise BuildError(
            f"{scenario.id} in {version} is not schema-valid: "
            + " | ".join(errors)
        )
    return BuildResult(version, xml, report)


def build_all(scenario: Scenario) -> list[BuildResult]:
    """Render a scenario in every edition it lists, in listed order."""
    return [build(scenario, version) for version in scenario.versions]


__all__ = [
    "ALIASES",
    "deep_merge",
    "BuildError",
    "BuildReport",
    "BuildResult",
    "WRAP_PREFERENCE",
    "build",
    "build_all",
]
