# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Prepare a parsed document for one namespace-preserving enveloped signature."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from pain001.security._dsig_verify import XMLDSIG_NS, _c14n, _etree, _parse
from pain001.xml.envelope import BAH_NAMESPACE


def _one_header(root: Any) -> Any | None:
    """Find the supported BAH by exact namespace; ambiguous headers are refused."""
    header = None
    for candidate in root.iter(f"{{{BAH_NAMESPACE}}}AppHdr"):
        if header is not None:
            raise ValueError("signing requires at most one AppHdr")
        header = candidate
    return header


def _signature_parent(root: Any) -> Any:
    """Use the BAH's empty Sgntr, or the root for a plain document."""
    header = _one_header(root)
    if header is None:
        return root
    tag = f"{{{BAH_NAMESPACE}}}Sgntr"
    containers = header.findall(tag)
    if len(containers) > 1:
        raise ValueError("signing requires at most one Sgntr")
    if containers:
        parent = containers[0]
        if len(parent) or (parent.text or "").strip():
            raise ValueError("the existing Sgntr must be empty")
        return parent
    parent = _etree().Element(tag)
    related = header.find(f"{{{BAH_NAMESPACE}}}Rltd")
    if related is None:
        header.append(parent)
    else:
        header.insert(header.index(related), parent)
    return parent


def _prepare_document(xml_content: str) -> tuple[Any, Any, str]:
    """Digest the parsed tree, including a new BAH container but no Signature."""
    tree = _parse(xml_content.encode("utf-8"))
    root = tree.getroot()
    if next(root.iter(f"{{{XMLDSIG_NS}}}Signature"), None) is not None:
        raise ValueError("the document already contains a Signature")
    parent = _signature_parent(root)
    digest = base64.b64encode(
        hashlib.sha256(_c14n(tree, None)).digest()
    ).decode("ascii")
    signature = _etree().Element(
        f"{{{XMLDSIG_NS}}}Signature", nsmap={"ds": XMLDSIG_NS}
    )
    parent.append(signature)
    return tree, signature, digest


def _serialize_document(tree: Any) -> str:
    """Serialize the same parsed tree without rewriting its namespace prefixes."""
    return bytes(
        _etree().tostring(tree, xml_declaration=True, encoding="UTF-8")
    ).decode("utf-8")
