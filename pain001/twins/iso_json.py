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

"""The ISO JSON twin of a pain.001 document.

The shape follows the ISO 20022 Registration Authority's *Generation of
JSON Schema Draft 2020-12 for ISO 20022:2013* (v2.0, June 2025):

* keys are the XML tag names, unchanged, under a ``Document`` root;
* an amount with a currency attribute is ``{"amt": "…", "Ccy": "…"}``;
* decimals, dates and times are strings exactly as the XML spells them;
* booleans are the strings ``"true"`` and ``"false"``;
* namespaces are not represented (the edition names the schema).

One rule is this project's, not the RA's: every element the schema
declares repeatable is always an array, even with one occurrence, so a
twin has one shape. The decoder accepts the RA's other form (a bare
value) as well.

Decoding goes through the XSD, so a twin that does not fit the edition
raises :class:`TwinError` rather than producing bad XML.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from functools import cache
from typing import Any

import xmlschema

from pain001.corpus.inventory import Inventory, inventory_for
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

#: The message family the twin layer covers (ADR-0005).
SUPPORTED_PREFIX = "pain.001."
_TEXT = "$"
_CCY = "@Ccy"
_XMLNS = "@xmlns"


class TwinError(ValueError):
    """The twin or the edition is not usable."""


def supported(version: str) -> bool:
    """True when ``version`` is a bundled pain.001 edition."""
    return version.startswith(SUPPORTED_PREFIX) and any(
        m.message_type == version
        for m in DEFAULT_TEMPLATE_REGISTRY.list_templates()
    )


def _check(version: str) -> None:
    """Raise unless ``version`` is a bundled pain.001 edition."""
    if not supported(version):
        raise TwinError(
            f"twins cover bundled pain.001 editions, not {version}"
        )


@cache
def _schema(version: str) -> xmlschema.XMLSchema:
    """The compiled XSD of an edition, cached."""
    xsd = DEFAULT_TEMPLATE_REGISTRY.get_template(version).xsd_path
    return xmlschema.XMLSchema(str(xsd))


@cache
def _shape(version: str) -> tuple[frozenset[str], frozenset[str]]:
    """The repeatable element paths and the boolean paths of an edition.

    Paths are relative to ``Document`` (``CstmrCdtTrfInitn/PmtInf``).
    """
    inventory: Inventory = inventory_for(version)
    repeatable = set()
    booleans = set()
    for entry in inventory.elements:
        rel = entry.path[len("/Document/") :]
        if entry.kind in ("simple", "complex") and entry.max_occurs != 1:
            repeatable.add(rel)
        if entry.primitive == "boolean":
            booleans.add(rel)
    return frozenset(repeatable), frozenset(booleans)


def _encode_node(node: Any, path: str, repeatable: frozenset[str]) -> Any:
    """Converter output to RA shape, always-array for repeatable paths."""
    if isinstance(node, list):
        return [_encode_node(item, path, repeatable) for item in node]
    if isinstance(node, bool):
        return "true" if node else "false"
    if isinstance(node, dict):
        if _TEXT in node:
            # simple content with attributes: only Ccy exists in pain.001
            return {"amt": node[_TEXT], "Ccy": node[_CCY]}
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == _XMLNS:
                continue
            child = f"{path}/{key}" if path else key
            encoded = _encode_node(value, child, repeatable)
            if child in repeatable and not isinstance(encoded, list):
                encoded = [encoded]
            out[key] = encoded
        return out
    return node


def to_iso_json(xml: str, version: str) -> dict[str, Any]:
    """The ISO JSON twin of a pain.001 document.

    Args:
        xml: The document text.
        version: Its edition, e.g. ``pain.001.001.09``.

    Returns:
        ``{"Document": {...}}`` in the RA convention with always-array
        normalisation.

    Raises:
        TwinError: If the edition is not a bundled pain.001 edition or
            the document does not validate against it.
    """
    _check(version)
    schema = _schema(version)
    try:
        raw = schema.to_dict(xml, decimal_type=str, validation="strict")
    except xmlschema.XMLSchemaException as exc:
        raise TwinError(f"not a valid {version} document: {exc}") from exc
    repeatable, _ = _shape(version)
    return {"Document": _encode_node(raw, "", repeatable)}


def _decode_node(node: Any, path: str, booleans: frozenset[str]) -> Any:
    """RA shape back to the converter's shape; bare values or arrays."""
    if isinstance(node, list):
        return [_decode_node(item, path, booleans) for item in node]
    if isinstance(node, dict):
        if set(node) == {"amt", "Ccy"}:
            return {_CCY: node["Ccy"], _TEXT: node["amt"]}
        return {
            key: _decode_node(
                value, f"{path}/{key}" if path else key, booleans
            )
            for key, value in node.items()
        }
    if path in booleans and isinstance(node, str):
        if node in ("true", "1"):
            return True
        if node in ("false", "0"):
            return False
        raise TwinError(f"{path}: {node!r} is not a boolean")
    return node


def from_iso_json(doc: dict[str, Any], version: str) -> str:
    """The pain.001 document of an ISO JSON twin.

    Args:
        doc: ``{"Document": {...}}`` in the RA convention; repeatable
            elements may be arrays or bare values, in any key order.
        version: The edition to encode against.

    Returns:
        The XML text, declared and indented, valid against the edition.

    Raises:
        TwinError: If the twin has no ``Document`` root, names an
            element the edition does not declare, or breaks a facet.
    """
    _check(version)
    if not isinstance(doc, dict) or set(doc) != {"Document"}:
        raise TwinError("a twin is an object with the single key 'Document'")
    _, booleans = _shape(version)
    schema = _schema(version)
    body = _decode_node(doc["Document"], "", booleans)
    body[_XMLNS] = schema.target_namespace
    try:
        element = schema.encode(
            body,
            converter=xmlschema.UnorderedConverter,
            validation="strict",
        )
    except xmlschema.XMLSchemaException as exc:
        raise TwinError(f"twin does not fit {version}: {exc}") from exc
    if not isinstance(element, ET.Element):  # pragma: no cover - strict raises
        raise TwinError(f"twin does not fit {version}")
    ET.register_namespace("", schema.target_namespace)
    ET.indent(element, space="  ")
    body_text = str(ET.tostring(element, encoding="unicode"))
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body_text + "\n"


__all__ = [
    "SUPPORTED_PREFIX",
    "TwinError",
    "from_iso_json",
    "supported",
    "to_iso_json",
]
