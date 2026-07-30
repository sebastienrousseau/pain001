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
    indent_xml(root)

    # short_empty_elements matches legacy ElementTree.write() behavior.
    xml_bytes: bytes = et.tostring(
        root,
        encoding="utf-8",
        method="xml",
        short_empty_elements=True,
    )

    xml_str: str = xml_bytes.decode("utf-8")

    # Double quotes and "UTF-8" capitalization keep the declaration
    # byte-for-byte identical to ElementTree.write() output.
    if include_declaration and not xml_str.startswith("<?xml"):
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

    # The legacy file-based writer ends with a newline; regression tests
    # compare output byte-for-byte.
    if not xml_str.endswith("\n"):
        xml_str += "\n"

    return xml_str
