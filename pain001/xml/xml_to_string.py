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

"""
This module provides utilities for converting XML ElementTree objects to strings.
Supports serverless/API architectures where in-memory XML processing is preferred.
"""

import xml.etree.ElementTree as et  # nosec B405

from pain001.xml.write_xml_to_file import indent_xml


def xml_to_string(root: et.Element, include_declaration: bool = True) -> str:
    """
    Convert an XML ElementTree Element to a formatted string.

    This function provides the same pretty-printing as write_xml_to_file,
    but returns the XML as a string instead of writing to disk.
    Ideal for serverless architectures, APIs, and in-memory processing.

    Parameters
    ----------
    root : xml.etree.ElementTree.Element
        The root element of the XML tree.
    include_declaration : bool, optional
        Whether to include the XML declaration (<?xml version="1.0" encoding="UTF-8"?>).
        Default is True.

    Returns
    -------
    str
        The formatted XML content as a UTF-8 string.

    Examples
    --------
    >>> from pain001.xml.create_root_element import create_root_element
    >>> root = create_root_element("pain.001.001.03")
    >>> xml_str = xml_to_string(root)
    >>> xml_str.startswith('<?xml version=')
    True
    """
    # Apply indentation in-place (same as write_xml_to_file)
    indent_xml(root)

    # Convert to bytes with proper encoding
    # Use short_empty_elements=True to match legacy ElementTree.write() behavior
    xml_bytes: bytes = et.tostring(
        root,
        encoding="utf-8",
        method="xml",
        short_empty_elements=True,
    )

    # Decode to string
    xml_str: str = xml_bytes.decode("utf-8")

    # Add XML declaration if requested (match ElementTree.write() format)
    # Use double quotes and UTF-8 capitalization for byte-for-byte compatibility
    if include_declaration and not xml_str.startswith("<?xml"):
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

    # Add trailing newline to match ElementTree.write() behavior
    # Legacy file-based writer adds newline at EOF - critical for regression tests
    if not xml_str.endswith("\n"):
        xml_str += "\n"

    return xml_str
