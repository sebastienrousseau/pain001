# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Validate XML documents against XSD schemas."""

import logging
from functools import lru_cache
from io import StringIO

import xmlschema
from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _get_cached_schema(xsd_file_path: str) -> xmlschema.XMLSchema:
    """Return a cached XMLSchema instance for the given XSD file path."""
    return xmlschema.XMLSchema(xsd_file_path)


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
    except (ParseError, OSError) as e:
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
    except (ParseError, OSError) as e:
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
    # Load XML string into an ElementTree object using defusedxml for security.
    try:
        xml_tree = defused_et.parse(StringIO(xml_content))
    except (ParseError, OSError) as e:
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
