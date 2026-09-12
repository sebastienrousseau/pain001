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

"""What an XSD can express, and how much of it a set of files uses.

An :class:`Inventory` lists every element path an ISO 20022 schema
declares, every attribute, every ``xs:any`` slot, and every
``xs:choice`` group with its branches, with the leaf facets (length,
pattern, enumeration, digits, bounds) a file must respect. It is the
yardstick ADR-0003 defines coverage against: every element path and
every choice branch hit by at least one file of a version's coverage
set, with a named exemption list.

:func:`coverage` measures a set of XML files against an inventory and
returns a :class:`CoverageReport`; ``scripts/corpus_coverage.py`` turns
that into the ``make corpus-coverage`` gate.

Paths are slash-joined local names from the root, ``/Document/...``;
attributes are ``path/@name``; an ``xs:any`` slot is ``path/*``. A
choice is identified by the path of the element that holds it, and a
branch by the local names of the elements that start it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import xmlschema
from defusedxml import ElementTree as defused_et
from xmlschema.validators import (
    XsdAnyElement,
    XsdComplexType,
    XsdElement,
    XsdGroup,
)

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

#: Descent stops when a complex type appears again on its own path.
#: ISO 20022 payment schemas are not recursive, so the cap is a guard,
#: not a tuning knob.
MAX_DEPTH = 64

_XSI = "{http://www.w3.org/2001/XMLSchema-instance}"

_FACET_NAMES = {
    "minLength": "min_length",
    "maxLength": "max_length",
    "length": "length",
    "totalDigits": "total_digits",
    "fractionDigits": "fraction_digits",
    "minInclusive": "min_inclusive",
    "maxInclusive": "max_inclusive",
    "minExclusive": "min_exclusive",
    "maxExclusive": "max_exclusive",
}


def _local(name: str) -> str:
    """Strip a ``{namespace}`` prefix from a qualified name."""
    return name.rsplit("}", 1)[-1]


@dataclass(frozen=True)
class ElementEntry:
    """One declared slot in a schema: element, attribute or ``xs:any``.

    Attributes:
        path: Slash-joined local names from ``/Document``.
        kind: ``complex``, ``simple``, ``attribute`` or ``any``.
        type_name: The schema type's local name, if it has one.
        min_occurs: Minimum occurrences at this position.
        max_occurs: Maximum occurrences, ``None`` for unbounded.
        primitive: The XSD primitive a simple value reduces to.
        facets: Normalised facets: ``enumeration`` (list), ``patterns``
            (list of regex strings) and the length, digit and bound
            facets keyed by their snake_case name.
    """

    path: str
    kind: str
    type_name: str | None = None
    min_occurs: int = 1
    max_occurs: int | None = 1
    primitive: str | None = None
    facets: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChoiceEntry:
    """An ``xs:choice`` group and the branches a file can take.

    Attributes:
        path: Path of the element whose content holds the choice.
        branches: One tuple per branch, holding the local names of the
            elements that branch starts with (``("*",)`` for ``xs:any``).
    """

    path: str
    branches: tuple[tuple[str, ...], ...]

    def branch_ids(self) -> list[str]:
        """Stable identifiers, ``path -> A+B``, one per branch."""
        return [f"{self.path} -> {'+'.join(b)}" for b in self.branches]


@dataclass(frozen=True)
class Inventory:
    """Everything one schema can express.

    Attributes:
        message_type: The message type the schema defines.
        namespace: The schema's target namespace.
        elements: Every element, attribute and ``xs:any`` slot.
        choices: Every ``xs:choice`` group.
    """

    message_type: str
    namespace: str
    elements: tuple[ElementEntry, ...]
    choices: tuple[ChoiceEntry, ...]

    def paths(self) -> frozenset[str]:
        """Every declared path, attributes and ``any`` slots included."""
        return frozenset(e.path for e in self.elements)

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready dict; :meth:`from_dict` reverses it."""
        return {
            "message_type": self.message_type,
            "namespace": self.namespace,
            "elements": [asdict(e) for e in self.elements],
            "choices": [
                {"path": c.path, "branches": [list(b) for b in c.branches]}
                for c in self.choices
            ],
        }

    def to_json(self, indent: int | None = 2) -> str:
        """The dict form as JSON text."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Inventory:
        """Rebuild an inventory from :meth:`to_dict` output.

        Args:
            data: The dict form of an inventory.

        Returns:
            The equivalent :class:`Inventory`.
        """
        return cls(
            message_type=data["message_type"],
            namespace=data["namespace"],
            elements=tuple(ElementEntry(**e) for e in data["elements"]),
            choices=tuple(
                ChoiceEntry(c["path"], tuple(tuple(b) for b in c["branches"]))
                for c in data["choices"]
            ),
        )


def _simple_facets(xsd_type: Any) -> tuple[str | None, dict[str, Any]]:
    """Return ``(primitive, facets)`` for a simple type or simple content."""
    simple = xsd_type if xsd_type.is_simple() else xsd_type.content
    primitive = getattr(simple, "primitive_type", None)
    facets: dict[str, Any] = {}
    enumeration = getattr(simple, "enumeration", None)
    if enumeration:
        facets["enumeration"] = list(enumeration)
    patterns = getattr(simple, "patterns", None)
    if patterns:
        facets["patterns"] = [p.attrib.get("value") for p in patterns]
    for key, facet in (getattr(simple, "facets", None) or {}).items():
        name = _FACET_NAMES.get(_local(key))
        value = getattr(facet, "value", None)
        if name is not None and value is not None:
            facets[name] = value if isinstance(value, int) else str(value)
    name = getattr(primitive, "name", None)
    return (_local(name) if name else None), facets


class _Walker:
    """Depth-first walk of a schema's content model."""

    def __init__(self) -> None:
        self.elements: list[ElementEntry] = []
        self.choices: list[ChoiceEntry] = []

    def group(
        self, group: XsdGroup, path: str, lineage: frozenset[Any], depth: int
    ) -> None:
        """Walk one model group, recording a choice if it is one."""
        if group.model == "choice":
            self.choices.append(ChoiceEntry(path, self._branches(group)))
        for item in group:
            if isinstance(item, XsdGroup):
                self.group(item, path, lineage, depth)
            elif isinstance(item, XsdAnyElement):
                self.elements.append(
                    ElementEntry(
                        f"{path}/*",
                        "any",
                        None,
                        item.min_occurs,
                        item.max_occurs,
                    )
                )
            else:
                self.element(item, path, lineage, depth)

    @staticmethod
    def _branches(group: XsdGroup) -> tuple[tuple[str, ...], ...]:
        """The local names each branch of a choice starts with."""
        branches: list[tuple[str, ...]] = []
        for item in group:
            if isinstance(item, XsdElement):
                branches.append((_local(item.name),))
            elif isinstance(item, XsdAnyElement):
                branches.append(("*",))
            else:
                branches.append(
                    tuple(
                        _local(x.name)
                        for x in item.iter_elements()
                        if isinstance(x, XsdElement)
                    )
                )
        return tuple(branches)

    def element(
        self,
        element: XsdElement,
        parent: str,
        lineage: frozenset[Any],
        depth: int,
    ) -> None:
        """Record one element and descend into its content."""
        path = f"{parent}/{_local(element.name)}"
        xsd_type = element.type
        complex_type = (
            xsd_type if isinstance(xsd_type, XsdComplexType) else None
        )
        simple = complex_type is None or complex_type.has_simple_content()
        primitive, facets = _simple_facets(xsd_type) if simple else (None, {})
        self.elements.append(
            ElementEntry(
                path,
                "simple" if simple else "complex",
                _local(xsd_type.name) if xsd_type.name else None,
                element.min_occurs,
                element.max_occurs,
                primitive,
                facets,
            )
        )
        if complex_type is None:
            return
        for name, attribute in complex_type.attributes.items():
            attr_type = attribute.type
            a_primitive, a_facets = _simple_facets(attr_type)
            type_name = getattr(attr_type, "name", None)
            self.elements.append(
                ElementEntry(
                    f"{path}/@{_local(name or '')}",
                    "attribute",
                    _local(type_name) if type_name else None,
                    1 if attribute.use == "required" else 0,
                    1,
                    a_primitive,
                    a_facets,
                )
            )
        content = complex_type.content
        if simple or not isinstance(content, XsdGroup):
            return
        key = complex_type.name or id(complex_type)
        if key in lineage or depth >= MAX_DEPTH:
            return
        self.group(content, path, lineage | {key}, depth + 1)


def build_inventory(xsd_path: str | Path, message_type: str) -> Inventory:
    """Inventory one schema file.

    Args:
        xsd_path: The XSD to walk; its root element must be ``Document``.
        message_type: The message type to label the inventory with.

    Returns:
        The schema's :class:`Inventory`.
    """
    schema = xmlschema.XMLSchema(str(xsd_path))
    root = schema.elements["Document"]
    walker = _Walker()
    walker.element(root, "", frozenset(), 0)
    return Inventory(
        message_type,
        schema.target_namespace or "",
        tuple(walker.elements),
        tuple(walker.choices),
    )


@cache
def inventory_for(message_type: str) -> Inventory:
    """The inventory of a bundled message type's XSD, cached.

    Args:
        message_type: A registered message type, e.g. ``pain.001.001.09``.

    Returns:
        The bundled schema's :class:`Inventory`. A message type that is
        not bundled propagates the registry's ``KeyError``.
    """
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    return build_inventory(meta.xsd_path, message_type)


def present_paths(source: str | Path) -> frozenset[str]:
    """The element and attribute paths one XML document uses.

    Args:
        source: A path to an XML file, or XML text.

    Returns:
        Paths in inventory form, namespaces stripped.
    """
    text = (
        Path(source).read_text(encoding="utf-8")
        if _is_path(source)
        else str(source)
    )
    root = defused_et.fromstring(text)
    found: set[str] = set()

    def visit(node: Any, parent: str) -> None:
        """Record ``node``, its attributes and its subtree."""
        path = f"{parent}/{_local(node.tag)}"
        found.add(path)
        for attribute in node.attrib:
            if attribute.startswith(_XSI):
                continue  # schemaLocation and friends are not content
            found.add(f"{path}/@{_local(attribute)}")
        for child in node:
            visit(child, path)

    visit(root, "")
    return frozenset(found)


def _is_path(source: str | Path) -> bool:
    """True for a filesystem path, False for XML text."""
    if isinstance(source, Path):
        return True
    return not source.lstrip().startswith("<")


@dataclass(frozen=True)
class CoverageReport:
    """How much of an inventory a set of files exercises.

    Attributes:
        message_type: The inventory's message type.
        sources: The files measured, as given.
        hit_paths: Declared paths at least one file uses.
        missing_paths: Declared paths no file uses, exemptions removed.
        hit_branches: Choice branch ids at least one file takes.
        missing_branches: Branch ids no file takes, exemptions removed.
        exempt: Paths and branch ids excluded from the gate, as given.
        unknown: Paths the files use that the inventory does not declare.
    """

    message_type: str
    sources: tuple[str, ...]
    hit_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]
    hit_branches: tuple[str, ...]
    missing_branches: tuple[str, ...]
    exempt: tuple[str, ...]
    unknown: tuple[str, ...]

    @property
    def path_percent(self) -> float:
        """Hit paths over declared paths, exemptions excluded."""
        total = len(self.hit_paths) + len(self.missing_paths)
        return 100.0 if total == 0 else 100.0 * len(self.hit_paths) / total

    @property
    def branch_percent(self) -> float:
        """Hit branches over declared branches, exemptions excluded."""
        total = len(self.hit_branches) + len(self.missing_branches)
        return 100.0 if total == 0 else 100.0 * len(self.hit_branches) / total

    @property
    def complete(self) -> bool:
        """True when nothing non-exempt is missing."""
        return not self.missing_paths and not self.missing_branches

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready dict with the percentages included."""
        data = asdict(self)
        data["path_percent"] = round(self.path_percent, 2)
        data["branch_percent"] = round(self.branch_percent, 2)
        data["complete"] = self.complete
        return data


def _branch_hit(
    choice: ChoiceEntry, branch: tuple[str, ...], present: frozenset[str]
) -> bool:
    """True when any element that starts ``branch`` is present."""
    if branch == ("*",):
        prefix = f"{choice.path}/"
        return any(p.startswith(prefix) for p in present)
    return any(f"{choice.path}/{name}" in present for name in branch)


def coverage(
    inventory: Inventory,
    sources: Iterable[str | Path],
    exemptions: Iterable[str] = (),
) -> CoverageReport:
    """Measure files against an inventory.

    Args:
        inventory: The yardstick.
        sources: XML files or XML texts; their paths are unioned.
        exemptions: Paths or branch ids (``path -> A+B``) to leave out
            of the missing lists. Unknown names are ignored.

    Returns:
        The :class:`CoverageReport`.
    """
    sources = list(sources)
    present: frozenset[str] = frozenset()
    for source in sources:
        present = present | present_paths(source)
    exempt = frozenset(exemptions)
    declared = inventory.paths()
    hit: list[str] = []
    missing: list[str] = []
    for entry in inventory.elements:
        if entry.kind == "any":
            prefix = entry.path[:-1]
            used = any(
                p.startswith(prefix) and p != prefix.rstrip("/")
                for p in present
            )
        else:
            used = entry.path in present
        if used:
            hit.append(entry.path)
        elif entry.path not in exempt:
            missing.append(entry.path)
    hit_branches: list[str] = []
    missing_branches: list[str] = []
    for choice in inventory.choices:
        for branch, branch_id in zip(
            choice.branches, choice.branch_ids(), strict=True
        ):
            if _branch_hit(choice, branch, present):
                hit_branches.append(branch_id)
            elif branch_id not in exempt:
                missing_branches.append(branch_id)
    unknown = sorted(
        p
        for p in present
        if p not in declared and not _under_any(p, inventory)
    )
    return CoverageReport(
        inventory.message_type,
        tuple(str(s) if _is_path(s) else "<inline>" for s in sources),
        tuple(hit),
        tuple(missing),
        tuple(hit_branches),
        tuple(missing_branches),
        tuple(sorted(exempt)),
        tuple(unknown),
    )


def _under_any(path: str, inventory: Inventory) -> bool:
    """True when ``path`` sits inside an ``xs:any`` slot."""
    return any(
        e.kind == "any" and path.startswith(e.path[:-1])
        for e in inventory.elements
    )


__all__ = [
    "MAX_DEPTH",
    "ChoiceEntry",
    "CoverageReport",
    "ElementEntry",
    "Inventory",
    "build_inventory",
    "coverage",
    "inventory_for",
    "present_paths",
]
