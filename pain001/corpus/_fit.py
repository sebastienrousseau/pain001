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

"""Conform a composed tree to one edition's inventory (the builder's pass 2).

Split out of :mod:`pain001.corpus.builder`, which re-exports
:data:`ALIASES` and :data:`WRAP_PREFERENCE`; see its docstring for what
each move does and how the :class:`~pain001.corpus.builder.BuildReport`
records it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pain001.corpus.inventory import ElementEntry, Inventory


class _Report(Protocol):
    """The lists of :class:`~pain001.corpus.builder.BuildReport` this pass fills.

    A protocol, not an import, so this module never imports the builder
    that imports it.
    """

    renamed: list[tuple[str, str]]
    wrapped: list[str]
    unwrapped: list[str]
    dropped: list[str]
    truncated: list[str]


#: Elements that changed name between editions but not meaning.
ALIASES: dict[str, tuple[str, ...]] = {
    "BIC": ("BICFI",),
    "BICFI": ("BIC",),
    "BICOrBEI": ("AnyBIC",),
    "AnyBIC": ("BICOrBEI",),
}
#: When a scalar meets a complex slot, the child that carries it.
WRAP_PREFERENCE: tuple[str, ...] = ("Cd", "Dt", "DtTm", "Tp", "Id")

Tree = dict[str, Any]


class _Fitter:
    """Fits a composed tree to one edition's inventory."""

    def __init__(self, inventory: Inventory, report: _Report) -> None:
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
        for name, value in node.items():
            self._place(name, value, path, declared, fitted)
        ordered = {name: fitted[name] for name in declared if name in fitted}
        for name, value in fitted.items():  # content under an xs:any slot
            if name not in ordered:
                ordered[name] = value
        return ordered

    def _place(
        self,
        name: str,
        value: Any,
        path: str,
        declared: dict[str, ElementEntry],
        fitted: Tree,
    ) -> None:
        """Fit one child into ``fitted``: renamed, passed through or dropped."""
        if name not in declared:
            alias = next(
                (a for a in ALIASES.get(name, ()) if a in declared), None
            )
            if alias is None:
                if path in self.any_slots:
                    fitted[name] = value  # free content under xs:any
                else:
                    self.report.dropped.append(f"{path}/{name}")
                return
            self.report.renamed.append((f"{path}/{name}", alias))
            name = alias
        value = self.value(value, f"{path}/{name}", declared[name])
        if value is not None and value != {} and value != []:
            fitted[name] = value

    def value(self, value: Any, path: str, entry: ElementEntry) -> Any:
        """Conform one value to its declared slot."""
        if value is None:
            return None
        if isinstance(value, list):
            return self._repeated(value, path, entry)
        if entry.kind == "simple":
            if isinstance(value, dict):
                return self._simple_from_dict(value, path, entry)
            return value
        if not isinstance(value, dict):
            return self._wrapped_scalar(value, path)
        fitted = self.tree(value, path)
        return fitted or None

    def _repeated(
        self, value: list[Any], path: str, entry: ElementEntry
    ) -> Any:
        """Fit each item, drop empties, and respect maxOccurs."""
        items = [self.value(v, path, entry) for v in value]
        items = [i for i in items if i is not None and i != {}]
        if entry.max_occurs is not None and len(items) > entry.max_occurs:
            self.report.truncated.append(path)
            items = items[: entry.max_occurs]
        if entry.max_occurs == 1:
            return items[0] if items else None
        return items

    def _simple_from_dict(
        self, value: dict[str, Any], path: str, entry: ElementEntry
    ) -> Any:
        """Keep a simple slot's text and attributes, or unwrap one level."""
        if "$" in value or any(k.startswith("@") for k in value):
            return {
                k: v for k, v in value.items() if k == "$" or k.startswith("@")
            }
        for pick in WRAP_PREFERENCE:
            if pick in value:
                self.report.unwrapped.append(path)
                return self.value(value[pick], path, entry)
        self.report.dropped.append(path)
        return None

    def _wrapped_scalar(self, value: Any, path: str) -> Any:
        """Wrap a scalar given for a complex slot in its declared choice."""
        declared = self.children.get(path, {})
        wrap: str | None
        if "DtTm" in declared and "Dt" in declared and "T" in str(value):
            wrap = "DtTm"
        else:
            wrap = next((p for p in WRAP_PREFERENCE if p in declared), None)
        if wrap is None:
            self.report.dropped.append(path)
            return None
        self.report.wrapped.append(path)
        return self.tree({wrap: value}, path)
