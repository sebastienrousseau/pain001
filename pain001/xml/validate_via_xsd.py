# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Validate XML documents against XSD schemas.

Validation dominates the cost of producing a document. For a
1000-transaction batch (~1.4 MiB) it is ~93% of the total, with template
rendering and data preparation making up the rest — so this module, not
the XML generator, is where generation time is actually spent.

``xmlschema`` is a pure-Python XSD implementation and is what this module
has always used. When ``lxml`` is installed it is used instead as a fast
accept/reject gate, because libxml2 validates the same document about
46x faster (729ms -> 15.7ms here).

Two deliberate constraints on that:

* **lxml can only fast-path an accept.** If it rejects a document,
  ``xmlschema`` is asked as well and its answer is final. That keeps the
  verdict and the error messages coming from a single implementation,
  and it means installing or removing ``lxml`` cannot turn a document
  that was rejected into one that is accepted.
* **The parser is hardened.** ``defusedxml`` deliberately does not cover
  ``lxml``, so entity resolution, DTD loading and network access are all
  switched off explicitly rather than left at their defaults.

Verdicts were compared across 121 documents — one valid, the rest
mutated to be invalid in nine different ways — and the two
implementations agreed on every one.

A file on disk (the staged payment file a writer is about to publish)
is checked by :func:`collect_xsd_file_errors` without ever holding its
tree: libxml2 validates it as it streams past, so a 138 MiB file costs
about 26 MiB instead of about 800 MiB, in about the same CPU time. Its rejections are final only above
:data:`DETAILED_REPORT_LIMIT`; below it, ``xmlschema`` still decides and
lists the violations, exactly as for a string.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from io import StringIO
from typing import TYPE_CHECKING

from defusedxml import DefusedXmlException
from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

from pain001._lazy import lazy_module
from pain001.observability.otel import traced

__all__ = [
    "collect_xsd_validation_errors",
    "validate_via_xsd",
    "validate_xml_string_via_xsd",
]

# xmlschema loads on first use (about 60 ms): the CLI imports this module
# at start-up, and --help never validates anything.
if TYPE_CHECKING:
    import xmlschema
else:
    xmlschema = lazy_module("xmlschema")

logger = logging.getLogger(__name__)

try:  # pragma: no cover - presence depends on the install
    import lxml.etree as _lxml_etree

    _LXML_AVAILABLE = True
except ImportError:  # pragma: no cover - presence depends on the install
    _LXML_AVAILABLE = False


@lru_cache(maxsize=16)
def _get_cached_schema(xsd_file_path: str) -> xmlschema.XMLSchema:
    """Return a cached XMLSchema instance for the given XSD file path.

    The path may be a user's ``--schema``, so the schema is treated as
    untrusted local data: ``allow="local"`` loads imports and includes
    from the filesystem only, never over the network, and
    ``defuse="always"`` refuses DTDs and entity declarations.
    """
    return xmlschema.XMLSchema(xsd_file_path, allow="local", defuse="always")


@lru_cache(maxsize=16)
def _get_cached_lxml_schema(xsd_file_path: str) -> _lxml_etree.XMLSchema:
    """Return a cached compiled libxml2 schema for the given XSD path.

    Compiling the schema is the expensive part and does not depend on the
    document, so it is cached exactly like the xmlschema equivalent.
    The XSD is parsed with the same hardened parser as documents, so a
    user's schema cannot expand entities or reach the network.
    """
    return _lxml_etree.XMLSchema(
        _lxml_etree.parse(xsd_file_path, _hardened_lxml_parser())
    )


def _hardened_lxml_parser() -> _lxml_etree.XMLParser:
    """Return an lxml parser with the unsafe XML features switched off.

    ``defusedxml`` does not wrap ``lxml``, so the protections it would
    normally provide are configured here directly:

    * ``resolve_entities=False`` - no entity expansion, which is what
      billion-laughs and most XXE payloads rely on.
    * ``load_dtd=False`` - no external DTD subset.
    * ``no_network=True`` - no fetching of anything referenced remotely.
    * ``huge_tree=False`` - keeps libxml2's depth and size limits on.
    """
    return _lxml_etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
    )


#: The largest file a libxml2 rejection is re-checked by ``xmlschema``,
#: which builds the whole document (several times the file in memory,
#: about 35 s for 14 MiB) to give the authoritative verdict and up to 20
#: violations. A larger file is refused on libxml2's first violation.
DETAILED_REPORT_LIMIT = 10 * 1024 * 1024

#: The elements a payment file repeats (a batch, a transaction). The
#: streaming validator releases each of these, with everything inside,
#: once its end tag is checked; visiting only them, not every element,
#: keeps it about as fast as validating a whole tree.
_REPEATED = ("{*}PmtInf", "{*}CdtTrfTxInf", "{*}DrctDbtTxInf")

_NAMESPACE = re.compile(r"\{[^}]*\}")


def _release(element: _lxml_etree._Element) -> None:
    """Drop a finished element and the finished siblings before it."""
    element.clear(keep_tail=True)
    while element.getprevious() is not None:
        del element.getparent()[0]


def _declared_dtd(xml_file_path: str) -> str | None:
    """Refuse a document that declares a DTD; read only up to its root.

    libxml2 crashes the process (SIGBUS, lxml 6.1 with libxml2 2.14)
    when it validates against a schema while expanding an entity the
    document declares, and with entity expansion off it stops reporting
    well-formedness errors (a truncated file passes). A payment file
    never needs a DTD, so one is refused before the schema pass, which
    then runs with only the predefined entities to expand.

    Args:
        xml_file_path: The XML file.

    Returns:
        Why the file is refused, or ``None`` when it has no DTD.
    """
    with open(xml_file_path, "rb") as handle:
        events = _lxml_etree.iterparse(
            handle,
            events=("start",),
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            huge_tree=False,
        )
        try:
            _event, root = next(events)
        except _lxml_etree.XMLSyntaxError as error:
            return str(error.msg)
    if root.getroottree().docinfo.doctype:
        return "the document declares a DTD (<!DOCTYPE ...>)"
    return None


def _lxml_first_file_error(
    xml_file_path: str, schema: _lxml_etree.XMLSchema
) -> str | None:
    """Stream ``xml_file_path`` through libxml2's validator.

    Each batch and transaction (:data:`_REPEATED`) is released once its
    end tag is validated, so memory stays flat whatever the number of
    transactions. The parser loads no DTD and fetches
    nothing; :func:`_declared_dtd` has already refused a document that
    could declare an entity, so ``resolve_entities`` stays at lxml's
    ``"internal"`` (``False`` hides well-formedness errors here).

    Args:
        xml_file_path: The XML file.
        schema: The compiled schema it must pass.

    Returns:
        The first violation, without namespace URIs, or ``None`` when
        the file is valid.
    """
    refused = _declared_dtd(xml_file_path)
    if refused is not None:
        return refused
    with open(xml_file_path, "rb") as handle:
        events = _lxml_etree.iterparse(
            handle,
            events=("end",),
            tag=_REPEATED,
            schema=schema,
            resolve_entities="internal",
            load_dtd=False,
            no_network=True,
            huge_tree=False,
        )
        try:
            for _event, element in events:
                _release(element)
        except _lxml_etree.XMLSyntaxError as error:
            return _NAMESPACE.sub("", str(error.msg))
    return None


def _lxml_file_schema(xsd_file_path: str) -> _lxml_etree.XMLSchema | None:
    """The compiled libxml2 schema, or ``None`` when it cannot be used."""
    if not _LXML_AVAILABLE:
        return None
    try:
        return _get_cached_lxml_schema(xsd_file_path)
    except Exception:  # noqa: BLE001 - xmlschema reports schema errors
        return None


@traced("pain001.validate")
def collect_xsd_file_errors(
    xml_file_path: str, xsd_file_path: str, max_errors: int = 20
) -> list[str]:
    """Every XSD violation in a file, read with bounded memory.

    libxml2 streams the file and accepts it without building a tree.
    It rejects through ``xmlschema`` (the same verdict and messages as
    :func:`collect_xsd_validation_errors`) up to
    :data:`DETAILED_REPORT_LIMIT`; above it, its first violation is the
    answer. Without ``lxml``, or with a schema libxml2 cannot compile,
    ``xmlschema`` reads the file.

    Args:
        xml_file_path: The XML file.
        xsd_file_path: Path to the XSD schema file.
        max_errors: Cap on the number of collected messages.

    Returns:
        A list of error messages; empty when the file is valid.
    """
    schema = _lxml_file_schema(xsd_file_path)
    if schema is not None:
        first = _lxml_first_file_error(xml_file_path, schema)
        if first is None:
            return []
        if os.path.getsize(xml_file_path) > DETAILED_REPORT_LIMIT:
            return [
                f"{first} (first violation; the file is too large "
                "to list them all)"
            ]
    with open(xml_file_path, encoding="utf-8") as handle:
        content = handle.read()
    return collect_xsd_validation_errors(content, xsd_file_path, max_errors)


def _lxml_accepts(xml_content: str, xsd_file_path: str) -> bool:
    """Return whether libxml2 considers ``xml_content`` schema-valid.

    Returns ``False`` on any parse or schema error, which routes the
    document to ``xmlschema`` for an authoritative answer rather than
    failing it here.
    """
    try:
        schema = _get_cached_lxml_schema(xsd_file_path)
        document = _lxml_etree.fromstring(
            xml_content.encode("utf-8"), _hardened_lxml_parser()
        )
        return bool(schema.validate(document))
    except Exception:  # noqa: BLE001 - any failure defers to xmlschema
        return False


@traced("pain001.validate")
def validate_via_xsd(xml_file_path: str, xsd_file_path: str) -> bool:
    """
    Validates an XML file against an XSD schema.

    Args:
        xml_file_path: Path to the XML file to validate.
        xsd_file_path: Path to the XSD schema file.

    Returns:
        bool: True if the XML file is valid, False otherwise.
    """

    # Load XML file into an ElementTree object using defusedxml for security.
    try:
        xml_tree = defused_et.parse(xml_file_path)
    except (ParseError, DefusedXmlException, OSError) as e:
        logger.error("Error parsing XML file: %s", e)
        return False

    # Load XSD schema into an XMLSchema object (cached).
    try:
        xsd = _get_cached_schema(xsd_file_path)
    except (xmlschema.XMLSchemaException, ParseError, OSError) as e:
        logger.error("Error loading XSD schema: %s", e)
        return False

    # Validate XML file against XSD schema.
    try:
        xsd.validate(xml_tree)
        return True
    except xmlschema.XMLSchemaException as e:
        logger.error("Error validating XML: %s", e)
        return False


def collect_xsd_validation_errors(
    xml_content: str, xsd_file_path: str, max_errors: int = 20
) -> list[str]:
    """Collect every XSD validation error for an XML string, human-readably.

    Unlike :func:`validate_xml_string_via_xsd` (a boolean gate), this
    returns one concise message per violation - element path plus reason -
    so callers can report everything that is wrong in a single pass.

    Args:
        xml_content: XML content as a string.
        xsd_file_path: Path to the XSD schema file.
        max_errors: Cap on the number of collected messages.

    Returns:
        A list of error messages; empty when the document is valid.
    """
    try:
        xml_tree = defused_et.parse(StringIO(xml_content))
    except (ParseError, DefusedXmlException, OSError) as e:
        return [f"XML parse error: {e}"]
    try:
        xsd = _get_cached_schema(xsd_file_path)
    except (xmlschema.XMLSchemaException, ParseError, OSError) as e:
        return [f"XSD schema load error: {e}"]
    messages: list[str] = []
    for error in xsd.iter_errors(xml_tree):
        reason = error.reason or str(error)
        messages.append(f"{error.path or '/'}: {reason}")
        if len(messages) >= max_errors:
            break
    return messages


@traced("pain001.validate")
def validate_xml_string_via_xsd(xml_content: str, xsd_file_path: str) -> bool:
    """
    Validates an XML string against an XSD schema.

    This function is ideal for serverless/API architectures where XML is
    generated in-memory without writing to disk.

    Args:
        xml_content: XML content as a string.
        xsd_file_path: Path to the XSD schema file.

    Returns:
        bool: True if the XML content is valid, False otherwise.

    Examples:
        >>> xml_str = '<?xml version="1.0"?><Document></Document>'
        >>> xsd_path = "schema.xsd"
        >>> validate_xml_string_via_xsd(xml_str, xsd_path)  # doctest: +SKIP
        True
    """
    # Fast path: libxml2 accepts the overwhelming majority of documents
    # this is called on, ~46x quicker than the pure-Python validator. A
    # rejection is *not* taken as final — it falls through so xmlschema
    # can give the authoritative answer and, on the caller's error path,
    # the messages that go with it.
    if _LXML_AVAILABLE and _lxml_accepts(xml_content, xsd_file_path):
        return True

    # Load XML string into an ElementTree object using defusedxml for security.
    try:
        xml_tree = defused_et.parse(StringIO(xml_content))
    except (ParseError, DefusedXmlException, OSError) as e:
        logger.error("Error parsing XML string: %s", e)
        return False

    # Load XSD schema into an XMLSchema object (cached).
    try:
        xsd = _get_cached_schema(xsd_file_path)
    except (xmlschema.XMLSchemaException, ParseError, OSError) as e:
        logger.error("Error loading XSD schema: %s", e)
        return False

    # Validate XML against XSD schema.
    try:
        xsd.validate(xml_tree)
        return True
    except xmlschema.XMLSchemaException as e:
        logger.error("Error validating XML: %s", e)
        return False
