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

"""Generate the schema coverage set of an edition (ADR-0003, WS3).

The coverage corpus proves what each XSD can express: every element
path and every choice branch appears in at least one file of the
edition's set, and every file is schema-valid. Nothing hand-written
could keep that promise for 1,700 paths per edition, so the set is
derived from the :class:`~pain001.corpus.inventory.Inventory`:

* every leaf gets a value derived from its facets: an enumeration's
  first member, a verified sample for each of the twelve patterns the
  ISO schemas use, the minimum length of a text, ``1.00`` for an amount,
  fixed dates, ``true`` for a flag;
* the first file carries every element once, taking the first branch
  of every choice; each following file carries only the subtrees that
  still hold an unhit path or branch (plus whatever is mandatory around
  them), taking the least-covered branch of every choice, until the
  :func:`~pain001.corpus.inventory.coverage` report is complete;
* every file must pass the edition's XSD before it is kept.

Later files are therefore small, and an edition needs a handful of
files: one per recipe plus one per extra choice branch.

The MDR cross-element rules (:mod:`pain001.corpus.rules.mdr`) shape
the set too, so every file is a payment the report would accept:
blocks allowed on PmtInf or on the transaction but not both are
steered like choice branches; the cheque path has its own recipes
(delivered to the creditor agent, or not), transfers never carry a
cheque instruction; intermediary agents and charges accounts pull in
their prerequisites; a mandate's amendment flag follows its details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pain001.corpus import identifiers as ids
from pain001.corpus.builder import _serialise
from pain001.corpus.inventory import (
    ChoiceEntry,
    CoverageReport,
    ElementEntry,
    Inventory,
    coverage,
    inventory_for,
)
from pain001.corpus.rules.mdr import evaluate_mdr
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.validate_via_xsd import collect_xsd_validation_errors

Tree = dict[str, Any]

#: A verified sample for every pattern the bundled schemas declare.
PATTERN_SAMPLES: dict[str, str] = {
    r"[0-9]{1,15}": "1",
    r"[0-9]{2}": "01",
    r"[A-Z]{2,2}": "DE",
    r"[A-Z]{3,3}": "EUR",
    r"[a-zA-Z0-9]{4}": "ABCD",
    r"[A-Z]{6,6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3,3}){0,1}": "BANKDEFFXXX",
    r"[A-Z0-9]{4,4}[A-Z]{2,2}[A-Z0-9]{2,2}([A-Z0-9]{3,3}){0,1}": "BANKDEFFXXX",
    r"[A-Z]{2,2}[0-9]{2,2}[a-zA-Z0-9]{1,30}": "DE89370400440532013000",
    r"\+[0-9]{1,3}-[0-9()+\-]{1,30}": "+49-3012345678",
    r"[A-Z0-9]{18,18}[0-9]{2,2}": ids.make_lei(1),
    r"[A-Z0-9]{18}[0-9]{2}[A-Z0-9]{0,32}": ids.make_lei(1),
    r"[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}": ids.make_uetr(
        1
    ),
}
PRIMITIVE_SAMPLES: dict[str, str] = {
    "date": "2026-01-02",
    "dateTime": "2026-01-02T09:00:00",
    "boolean": "true",
    "gYear": "2026",
    "base64Binary": "AQID",
}
#: The element written into an ``xs:any`` slot.
ANY_CONTENT = {"Data": "x"}


@dataclass(frozen=True)
class Recipe:
    """How one file of a set is shaped to satisfy the MDR rules.

    Paths are relative to ``PmtInf`` (``CdtTrfTxInf/ChqInstr``).

    Attributes:
        name: Short label.
        pins: Values that override the facet sample at a path.
        forbid: Paths never emitted.
        require: Paths always emitted, even in a sparse file.
    """

    name: str
    pins: dict[str, str]
    forbid: frozenset[str] = frozenset()
    require: frozenset[str] = frozenset()


#: Blocks allowed on PmtInf or on the transaction, never both.
EXCLUSIVE: dict[str, tuple[tuple[str, str], ...]] = {
    "pain.001": (
        ("PmtTpInf", "CdtTrfTxInf/PmtTpInf"),
        ("ChrgBr", "CdtTrfTxInf/ChrgBr"),
        ("UltmtDbtr", "CdtTrfTxInf/UltmtDbtr"),
        ("InstrForDbtrAgt", "CdtTrfTxInf/InstrForDbtrAgt"),
    ),
    "pain.008": (
        ("PmtTpInf", "DrctDbtTxInf/PmtTpInf"),
        ("ChrgBr", "DrctDbtTxInf/ChrgBr"),
        ("UltmtCdtr", "DrctDbtTxInf/UltmtCdtr"),
        ("CdtrSchmeId", "DrctDbtTxInf/DrctDbtTx/CdtrSchmeId"),
    ),
}
#: An element that, when emitted, needs its sibling emitted too.
PREREQUISITES: dict[str, str] = {
    "IntrmyAgt1Acct": "IntrmyAgt1",
    "IntrmyAgt2Acct": "IntrmyAgt2",
    "IntrmyAgt3Acct": "IntrmyAgt3",
    "IntrmyAgt2": "IntrmyAgt1",
    "IntrmyAgt3": "IntrmyAgt2",
    "ChrgsAcctAgt": "ChrgsAcct",
}
RECIPES: dict[str, tuple[Recipe, ...]] = {
    "pain.001": (
        Recipe(
            "transfer",
            {"PmtMtd": "TRF", "CdtTrfTxInf/InstrForCdtrAgt/Cd": "PHOB"},
            forbid=frozenset({"CdtTrfTxInf/ChqInstr"}),
            require=frozenset({"CdtTrfTxInf/CdtrAcct"}),
        ),
        Recipe(
            "cheque-to-agent",
            {
                "PmtMtd": "CHK",
                "CdtTrfTxInf/ChqInstr/ChqTp": "DRFT",
                "CdtTrfTxInf/ChqInstr/DlvryMtd/Cd": "MLFA",
                "CdtTrfTxInf/InstrForCdtrAgt/Cd": "CHQB",
            },
            forbid=frozenset(
                {
                    "CdtTrfTxInf/CdtrAcct",
                    "CdtTrfTxInf/ChqInstr/DlvryMtd/Prtry",
                }
            ),
            require=frozenset(
                {
                    "CdtTrfTxInf/ChqInstr",
                    "CdtTrfTxInf/ChqInstr/DlvryMtd",
                    "CdtTrfTxInf/CdtrAgt",
                    "CdtTrfTxInf/Cdtr",
                }
            ),
        ),
        Recipe(
            "cheque-no-agent",
            {
                "PmtMtd": "CHK",
                "CdtTrfTxInf/ChqInstr/ChqTp": "DRFT",
                "CdtTrfTxInf/InstrForCdtrAgt/Cd": "CHQB",
            },
            forbid=frozenset(
                {
                    "CdtTrfTxInf/CdtrAcct",
                    "CdtTrfTxInf/CdtrAgt",
                    "CdtTrfTxInf/CdtrAgtAcct",
                    "CdtTrfTxInf/ChqInstr/DlvryMtd/Cd",
                }
            ),
            require=frozenset(
                {
                    "CdtTrfTxInf/ChqInstr",
                    "CdtTrfTxInf/ChqInstr/DlvryMtd",
                    "CdtTrfTxInf/Cdtr",
                }
            ),
        ),
    ),
    "pain.008": (Recipe("collection", {"PmtMtd": "DD"}),),
}


class CoverageBuildError(ValueError):
    """A generated file did not validate, or a facet has no sample."""


def sample_value(entry: ElementEntry) -> str:
    """A schema-valid value for a leaf, from its facets.

    Args:
        entry: A ``simple`` or ``attribute`` inventory entry.

    Returns:
        The value.

    Raises:
        CoverageBuildError: If a pattern has no sample in the table.
    """
    facets = entry.facets
    if "enumeration" in facets:
        return str(facets["enumeration"][0])
    for pattern in facets.get("patterns", []):
        if pattern not in PATTERN_SAMPLES:
            raise CoverageBuildError(
                f"{entry.path}: no sample for pattern {pattern!r}"
            )
        return PATTERN_SAMPLES[pattern]
    if entry.primitive == "decimal":
        return "1.00" if facets.get("fraction_digits", 1) else "1"
    if entry.primitive in PRIMITIVE_SAMPLES:
        return PRIMITIVE_SAMPLES[entry.primitive]
    length = int(facets.get("min_length", 1))
    return ("Text" * ((length // 4) + 1))[: max(length, 1)]


@dataclass(frozen=True)
class CoverageSet:
    """A generated set and its report."""

    version: str
    files: tuple[str, ...]
    report: CoverageReport


class _Planner:
    """Emits one file of the set from the inventory."""

    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory
        self.pmtinf = inventory.elements[1].path + "/PmtInf"
        self.recipe = Recipe("plain", {})
        self.sides: dict[int, int] = {}
        self.message = inventory.message_type[:8]
        self.children: dict[str, list[ElementEntry]] = {}
        self.attributes: dict[str, list[ElementEntry]] = {}
        self.entries: dict[str, ElementEntry] = {}
        self.any_slots: set[str] = set()
        for entry in inventory.elements:
            parent = entry.path.rsplit("/", 1)[0]
            self.entries[entry.path] = entry
            if entry.kind == "attribute":
                self.attributes.setdefault(parent, []).append(entry)
            elif entry.kind == "any":
                self.any_slots.add(parent)
            else:
                self.children.setdefault(parent, []).append(entry)
        self.choices: dict[str, list[ChoiceEntry]] = {}
        for choice in inventory.choices:
            self.choices.setdefault(choice.path, []).append(choice)
        # which paths and branch ids live under each path, for pruning
        self.descendants: dict[str, set[str]] = {}
        for entry in inventory.elements:
            for ancestor in _ancestors(entry.path):
                self.descendants.setdefault(ancestor, set()).add(entry.path)
        for choice in inventory.choices:
            for branch_id in choice.branch_ids():
                for ancestor in _ancestors(choice.path) | {choice.path}:
                    self.descendants.setdefault(ancestor, set()).add(branch_id)

    def _rel(self, path: str) -> str:
        """``path`` relative to PmtInf, or the empty string above it."""
        prefix = self.pmtinf + "/"
        return path[len(prefix) :] if path.startswith(prefix) else ""

    def _forbidden(self, path: str) -> bool:
        """True when the recipe or the chosen exclusive side bans ``path``."""
        rel = self._rel(path)
        if rel in self.recipe.forbid:
            return True
        for index, pair in enumerate(EXCLUSIVE.get(self.message, ())):
            if rel == pair[1 - self.sides.get(index, 0)]:
                return True
        return False

    def emit(
        self,
        path: str,
        picks: dict[str, int],
        unhit: set[str] | None,
    ) -> Tree:
        """The subtree at ``path``.

        Args:
            path: The element to emit.
            picks: Branch index per choice id (``path#n``).
            unhit: Items still to cover; ``None`` means emit everything.

        Returns:
            The tree, ``$``/``@`` keys for simple content.
        """
        tree: Tree = {}
        for attribute in self.attributes.get(path, []):
            name = attribute.path.rsplit("/@", 1)[1]
            tree[f"@{name}"] = sample_value(attribute)
        entry = self.entries[path]
        if entry.kind == "simple":
            tree["$"] = self.recipe.pins.get(
                self._rel(path), sample_value(entry)
            )
            return tree
        if path in self.any_slots:
            tree.update(ANY_CONTENT)
        wanted: list[str] = []
        for child in self.children.get(path, []):
            name = child.path.rsplit("/", 1)[1]
            if self._forbidden(child.path):
                continue
            if not self._chosen(path, name, picks):
                continue
            below = self.descendants.get(child.path, set()) | {child.path}
            if (
                unhit is not None
                and child.min_occurs == 0
                and self._rel(child.path) not in self.recipe.require
                and not below & unhit
            ):
                continue
            wanted.append(name)
        for name in list(wanted):
            needed = PREREQUISITES.get(name)
            if (
                needed
                and needed not in wanted
                and f"{path}/{needed}" in self.entries
                and not self._forbidden(f"{path}/{needed}")
            ):
                wanted.append(needed)
        for child in self.children.get(path, []):
            name = child.path.rsplit("/", 1)[1]
            if name in wanted:
                tree[name] = self.emit(child.path, picks, unhit)
        if path.endswith("/MndtRltdInf") and "AmdmntInd" in tree:
            flag = "true" if "AmdmntInfDtls" in tree else "false"
            tree["AmdmntInd"] = {"$": flag}
        return tree

    def pick_sides(self, unhit: set[str] | None) -> dict[int, int]:
        """For every exclusive pair, the side that still leads somewhere unhit.

        Args:
            unhit: Items still to cover, or ``None`` for the first file.

        Returns:
            Side index (0 for PmtInf, 1 for the transaction) per pair.
        """
        sides: dict[int, int] = {}
        for index, pair in enumerate(EXCLUSIVE.get(self.message, ())):
            sides[index] = 0
            if unhit is None:
                continue
            for side, rel in enumerate(pair):
                full = f"{self.pmtinf}/{rel}"
                if (self.descendants.get(full, set()) | {full}) & unhit:
                    sides[index] = side
                    break
        return sides

    def _chosen(self, path: str, name: str, picks: dict[str, int]) -> bool:
        """True unless a choice at ``path`` mentions ``name`` in another branch.

        A picked branch whose elements the recipe forbids is replaced by
        the first branch that has an allowed element, so a choice never
        renders empty.
        """
        for index, choice in enumerate(self.choices.get(path, [])):
            members = [n for branch in choice.branches for n in branch]
            if name not in members:
                continue
            picked = choice.branches[picks.get(f"{path}#{index}", 0)]
            if all(self._forbidden(f"{path}/{n}") for n in picked):
                picked = next(
                    (
                        b
                        for b in choice.branches
                        if not all(self._forbidden(f"{path}/{n}") for n in b)
                    ),
                    picked,
                )
            if name not in picked:
                return False
        return True

    def pick_branches(self, unhit: set[str] | None) -> dict[str, int]:
        """For every choice, the branch that still leads somewhere unhit.

        The first file (``unhit`` is ``None``) takes every first branch.
        Later files prefer a branch whose own id is unhit, then one with
        an unhit path or branch below it, so nested choices under a
        branch already taken once are still reached; otherwise the first.

        Args:
            unhit: Items still to cover, or ``None`` for the first file.

        Returns:
            Branch index per choice id (``path#n``).
        """
        picks: dict[str, int] = {}
        for path, choices in self.choices.items():
            for index, choice in enumerate(choices):
                picks[f"{path}#{index}"] = 0
                if unhit is None:
                    continue
                ids_ = choice.branch_ids()
                own = [i for i, b in enumerate(ids_) if b in unhit]
                if own:
                    picks[f"{path}#{index}"] = own[0]
                    continue
                for i, branch in enumerate(choice.branches):
                    below: set[str] = set()
                    for name in branch:
                        child = f"{path}/{name}"
                        below |= self.descendants.get(child, set()) | {child}
                    if below & unhit:
                        picks[f"{path}#{index}"] = i
                        break
        return picks


def _ancestors(path: str) -> set[str]:
    """Every proper ancestor path of ``path``."""
    found: set[str] = set()
    while "/" in path:
        path = path.rsplit("/", 1)[0]
        if path:
            found.add(path)
    return found


def build_coverage_set(version: str, max_files: int = 16) -> CoverageSet:
    """Generate the coverage set of a bundled edition.

    Args:
        version: The message type.
        max_files: Safety cap on the number of files.

    Returns:
        The :class:`CoverageSet`; its report is complete unless the cap
        was hit.

    Raises:
        CoverageBuildError: If a generated file fails the XSD.
    """
    inventory = inventory_for(version)
    planner = _Planner(inventory)
    root_path = inventory.elements[1].path  # /Document/<root>
    root_name = root_path.rsplit("/", 1)[1]
    xsd = str(DEFAULT_TEMPLATE_REGISTRY.get_template(version).xsd_path)
    files: list[str] = []
    hit_paths: set[str] = set()
    hit_branches: set[str] = set()
    all_items = inventory.paths() | {
        b for c in inventory.choices for b in c.branch_ids()
    }
    for recipe in RECIPES[planner.message]:
        planner.recipe = recipe
        while len(files) < max_files:
            unhit = (
                None
                if not files
                else set(all_items - hit_paths - hit_branches)
            )
            planner.sides = planner.pick_sides(unhit)
            picks = planner.pick_branches(unhit)
            tree = planner.emit(root_path, picks, unhit)
            xml = _serialise(root_name, tree, inventory.namespace)
            errors = collect_xsd_validation_errors(xml, xsd, max_errors=5)
            if errors:
                raise CoverageBuildError(
                    f"{version} set file {len(files) + 1} ({recipe.name}) is "
                    "not schema-valid: " + " | ".join(errors)
                )
            broken = evaluate_mdr(xml)
            if broken:
                raise CoverageBuildError(
                    f"{version} set file {len(files) + 1} ({recipe.name}) "
                    "breaks "
                    + "; ".join(f"{f.rule_id} at {f.path}" for f in broken[:5])
                )
            report = coverage(inventory, [*files, xml])
            new_hits = (set(report.hit_paths) - hit_paths) | (
                set(report.hit_branches) - hit_branches
            )
            if not new_hits:
                break
            files.append(xml)
            hit_paths = set(report.hit_paths)
            hit_branches = set(report.hit_branches)
            if report.complete:
                break
        if len(files) >= max_files or coverage(inventory, files).complete:
            break
    return CoverageSet(version, tuple(files), coverage(inventory, files))


__all__ = [
    "ANY_CONTENT",
    "PATTERN_SAMPLES",
    "PRIMITIVE_SAMPLES",
    "CoverageBuildError",
    "CoverageSet",
    "build_coverage_set",
    "sample_value",
]
