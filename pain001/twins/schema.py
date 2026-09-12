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

"""JSON Schema 2020-12 for the ISO JSON twin of a pain.001 edition.

Generated from the schema inventory by the rules of the ISO 20022
Registration Authority's *Generation of JSON Schema Draft 2020-12 for
ISO 20022:2013* (v2.0, June 2025):

* the root requires ``Document``, which requires the message block;
* a component is an object with ``additionalProperties: false``,
  ``required`` for its mandatory children and ``minProperties: 1``
  when it has none;
* a choice is an object with exactly one property;
* a repeatable element is ``anyOf`` a single item and a bounded array,
  so the RA's bare-value form and this project's always-array twin both
  validate;
* an amount with a currency attribute is ``{"amt", "Ccy"}``;
* every simple value is a string: enumerations become ``enum``, text
  lengths ``minLength``/``maxLength``, XSD patterns are anchored, decimals
  get a pattern built from their total and fraction digits and their
  lower bound, dates and times get the RA's patterns, booleans allow
  ``true``, ``false``, ``1`` and ``0``;
* the supplementary-data envelope is open.

Definitions are keyed by ISO type name under ``$defs`` (the RA uses
``$anchor``; the content is the same). No tool generates this from an
XSD; the inventory already carries every facet the rules consume.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

from pain001.corpus.inventory import ElementEntry, Inventory, inventory_for
from pain001.twins.iso_json import TwinError, _check

#: Where the committed schemas live.
SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas" / "iso-json"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
DATE_PATTERN = r"^-?[0-9]{4}-[0-9]{2}-[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})?$"
DATETIME_PATTERN = (
    r"^-?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?$"
)
YEAR_PATTERN = r"^-?[0-9]{4}(Z|[+-][0-9]{2}:[0-9]{2})?$"
BOOLEAN_VALUES = ["true", "false", "1", "0"]


def decimal_pattern(facets: dict[str, Any]) -> str:
    """The RA-style pattern for a decimal from its facets.

    At most ``total_digits`` digits in all, at most ``fraction_digits``
    of them after the point; leading and trailing zeros count, as the RA
    document says; a sign is allowed only when no lower bound of zero
    forbids it; ``5.`` and ``.5`` are accepted like the RA's algebra.

    Args:
        facets: ``total_digits``, ``fraction_digits`` and optional
            ``min_inclusive``.

    Returns:
        An anchored ECMA regular expression.
    """
    total = int(facets.get("total_digits", 18))
    fraction = int(facets.get("fraction_digits", 0))
    sign = "[+]?" if str(facets.get("min_inclusive", "")) == "0" else "[+-]?"
    whole = rf"[0-9]{{1,{total}}}"
    if not fraction:
        return rf"^{sign}{whole}$"
    with_point = rf"(?=[0-9.]{{2,{total + 1}}}$)[0-9]*\.[0-9]{{0,{fraction}}}"
    return rf"^{sign}(?:{whole}|{with_point})$"


def _simple_schema(entry: ElementEntry) -> dict[str, Any]:
    """The schema of one simple value, always a string."""
    facets = entry.facets
    out: dict[str, Any] = {"type": "string"}
    if entry.primitive == "boolean":
        out["enum"] = BOOLEAN_VALUES
        return out
    if entry.primitive == "decimal":
        out["pattern"] = decimal_pattern(facets)
        return out
    if entry.primitive == "date":
        out["pattern"] = DATE_PATTERN
        return out
    if entry.primitive == "dateTime":
        out["pattern"] = DATETIME_PATTERN
        return out
    if entry.primitive == "gYear":
        out["pattern"] = YEAR_PATTERN
        return out
    if "enumeration" in facets:
        out["enum"] = list(facets["enumeration"])
        return out
    if "min_length" in facets:
        out["minLength"] = int(facets["min_length"])
    if "max_length" in facets:
        out["maxLength"] = int(facets["max_length"])
    patterns = facets.get("patterns", [])
    if patterns:
        out["pattern"] = f"^(?:{patterns[0]})$"
    return out


def _occurs(entry: ElementEntry, item: dict[str, Any]) -> dict[str, Any]:
    """Wrap ``item`` in the RA's single-or-array form when repeatable."""
    if entry.max_occurs == 1:
        return item
    array: dict[str, Any] = {
        "type": "array",
        "minItems": max(1, int(entry.min_occurs)),
        "items": item,
    }
    if entry.max_occurs is not None:
        array["maxItems"] = int(entry.max_occurs)
    return {"anyOf": [item, array]}


class _Generator:
    """Builds the schema of one edition from its inventory."""

    def __init__(self, inventory: Inventory) -> None:
        self.inventory = inventory
        self.children: dict[str, list[ElementEntry]] = {}
        self.attributes: dict[str, list[ElementEntry]] = {}
        self.any_slots: set[str] = set()
        for entry in inventory.elements:
            parent = entry.path.rsplit("/", 1)[0]
            if entry.kind == "attribute":
                self.attributes.setdefault(parent, []).append(entry)
            elif entry.kind == "any":
                self.any_slots.add(parent)
            else:
                self.children.setdefault(parent, []).append(entry)
        self.choices = {c.path: c for c in inventory.choices}
        self.defs: dict[str, dict[str, Any]] = {}

    def _ref(self, entry: ElementEntry) -> dict[str, Any]:
        """A reference to the entry's type definition, defining it once."""
        name = entry.type_name or entry.path.rsplit("/", 1)[1]
        if name not in self.defs:
            self.defs[name] = {}  # placeholder against recursion
            self.defs[name] = self._define(entry)
        return {"$ref": f"#/$defs/{name}"}

    def _define(self, entry: ElementEntry) -> dict[str, Any]:
        """The definition of the entry's type."""
        attributes = self.attributes.get(entry.path, [])
        if entry.kind == "simple" and not attributes:
            return _simple_schema(entry)
        if entry.kind == "simple":
            # the only attribute in pain.001 is Ccy: the RA's amount object
            return {
                "type": "object",
                "additionalProperties": False,
                "required": ["amt", "Ccy"],
                "properties": {
                    "amt": _simple_schema(entry),
                    "Ccy": _simple_schema(attributes[0]),
                },
            }
        if entry.path in self.any_slots:
            return {"type": "object", "description": "ExternalSchema"}
        properties: dict[str, Any] = {}
        required: list[str] = []
        for child in self.children.get(entry.path, []):
            name = child.path.rsplit("/", 1)[1]
            properties[name] = _occurs(child, self._ref(child))
            if int(child.min_occurs) >= 1:
                required.append(name)
        out: dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        }
        if entry.path in self.choices:
            out["minProperties"] = 1
            out["maxProperties"] = 1
        elif required:
            out["required"] = required
        else:
            out["minProperties"] = 1
        return out

    def build(self) -> dict[str, Any]:
        """The complete schema document."""
        root = self.inventory.elements[1]  # /Document/<message>
        message = root.path.rsplit("/", 1)[1]
        self.defs["Document"] = {
            "type": "object",
            "additionalProperties": False,
            "required": [message],
            "properties": {message: self._ref(root)},
        }
        version = self.inventory.message_type
        return {
            "$schema": DRAFT,
            "$id": f"urn:iso:std:iso:20022:tech:json:{version}",
            "title": f"ISO JSON twin of {version}",
            "description": (
                "Generated by pain001 from the ISO 20022 schema by the rules "
                "of the Registration Authority's JSON Schema Draft 2020-12 "
                "generation recommendation (v2.0, June 2025)."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["Document"],
            "properties": {"Document": {"$ref": "#/$defs/Document"}},
            "$defs": dict(sorted(self.defs.items())),
        }


@cache
def generate_schema(version: str) -> dict[str, Any]:
    """Generate the twin schema of an edition from its inventory.

    Args:
        version: A bundled pain.001 edition.

    Returns:
        The JSON Schema document; a non-pain.001 edition is refused with
        :class:`TwinError` by the shared check.
    """
    _check(version)
    return _Generator(inventory_for(version)).build()


def iso_json_schema(version: str) -> dict[str, Any]:
    """The committed twin schema of an edition, or the generated one.

    Args:
        version: A bundled pain.001 edition.

    Returns:
        The JSON Schema document.
    """
    _check(version)
    path = SCHEMA_DIR / f"{version}.schema.json"
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    return generate_schema(version)


def _leaves(
    error: jsonschema.ValidationError,
) -> list[jsonschema.ValidationError]:
    """The deepest errors under an ``anyOf`` failure.

    A repeatable element is ``anyOf`` an item and an array, so a bad value
    inside it surfaces as the whole array failing; the sub-errors say
    where, and the deepest of them is the finding a reader wants.
    """
    if not error.context:
        return [error]
    found: list[jsonschema.ValidationError] = []
    for child in error.context:
        found.extend(_leaves(child))
    deepest = max(len(list(e.absolute_path)) for e in found)
    return [e for e in found if len(list(e.absolute_path)) == deepest]


def validate_iso_json(doc: Any, version: str) -> list[str]:
    """Validate a twin against its edition's schema.

    Args:
        doc: The twin.
        version: The edition.

    Returns:
        Findings as ``<json path>: <message>``, deepest first within each
        failure; empty when valid.
    """
    validator = jsonschema.Draft202012Validator(iso_json_schema(version))
    findings: set[str] = set()
    for error in validator.iter_errors(doc):
        for leaf in _leaves(error):
            where = "/" + "/".join(str(p) for p in leaf.absolute_path)
            findings.add(f"{where}: {leaf.message[:160]}")
    return sorted(findings)


def schema_text(version: str) -> str:
    """The generated schema as the text the repository commits."""
    return json.dumps(generate_schema(version), indent=2) + "\n"


__all__ = [
    "BOOLEAN_VALUES",
    "DATE_PATTERN",
    "DATETIME_PATTERN",
    "SCHEMA_DIR",
    "TwinError",
    "decimal_pattern",
    "generate_schema",
    "iso_json_schema",
    "schema_text",
    "validate_iso_json",
]
