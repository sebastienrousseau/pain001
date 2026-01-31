from functools import lru_cache
from io import StringIO

import xmlschema
from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError


@lru_cache(maxsize=16)
def _get_cached_schema(xsd_file_path: str) -> xmlschema.XMLSchema:
    """Return a cached XMLSchema instance for the given XSD file path."""
    return xmlschema.XMLSchema(xsd_file_path)


# Copyright (C) 2023-2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


def validate_via_xsd(xml_file_path: str, xsd_file_path: str) -> bool:
    """
    Validates an XML file against an XSD schema.

    Args:
        xml_file_path (str): Path to the XML file to validate.
        xsd_file_path (str): Path to the XSD schema file.

    Returns:
        bool: True if the XML file is valid, False otherwise.
    """

    # Load XML file into an ElementTree object using defusedxml for security.
    try:
        xml_tree = defused_et.parse(xml_file_path)
    except (ParseError, OSError) as e:
        print(f"Error parsing XML file: {e}")
        return False

    # Load XSD schema into an XMLSchema object (cached).
    try:
        xsd = _get_cached_schema(xsd_file_path)
    except (xmlschema.XMLSchemaException, ParseError, OSError) as e:
        print(f"Error loading XSD schema: {e}")
        return False

    # Validate XML file against XSD schema.
    try:
        xsd.validate(xml_tree)
        return True
    except xmlschema.XMLSchemaException as e:
        print(f"Error validating XML: {e}")
        return False


def validate_xml_string_via_xsd(xml_content: str, xsd_file_path: str) -> bool:
    """
    Validates an XML string against an XSD schema.

    This function is ideal for serverless/API architectures where XML is
    generated in-memory without writing to disk.

    Args:
        xml_content (str): XML content as a string.
        xsd_file_path (str): Path to the XSD schema file.

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
        print(f"Error parsing XML string: {e}")
        return False

    # Load XSD schema into an XMLSchema object (cached).
    try:
        xsd = _get_cached_schema(xsd_file_path)
    except (xmlschema.XMLSchemaException, ParseError, OSError) as e:
        print(f"Error loading XSD schema: {e}")
        return False

    # Validate XML against XSD schema.
    try:
        xsd.validate(xml_tree)
        return True
    except xmlschema.XMLSchemaException as e:
        print(f"Error validating XML: {e}")
        return False
