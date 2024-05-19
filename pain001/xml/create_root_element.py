# Copyright (C) 2023-2024 Sebastien Rousseau.
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

# pylint: disable=C0301

"""
Module for creating XML payment initiation message documents compliant with
the ISO 20022 standard. The generated XML documents include essential
namespaces and schema locations.

Note: This module does not include additional security features for XML
parsing. It is advisable to consider measures to prevent XML vulnerabilities
when using it.
"""

import xml.etree.ElementTree as et

# Namespace and schema-related constants
NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:"
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"


def create_root_element(message_type: str) -> et.Element:
    """
    Creates the root Element for a payment initiation XML document based on the
    specified message type. The function sets the required namespaces and
    schema locations.

    Args:
        message_type (str):
        Specifies the message type, for example, "pain.001.001.09". This is
        used to construct the namespace and schema location attributes.

    Returns:
        et.Element:
        The root Element node for the XML document, configured with the
        necessary namespaces and schema location attributes.

    Examples:
        >>> create_root_element("pain.001.001.09")
        <Element 'Document' at 0x7f8c0a309db0>
    """

    # Create the root element using the ElementTree library
    root = et.Element("Document")

    # Add xmlns (XML Namespace) and xmlns:xsi (XML Schema Instance) attributes
    # to the root element
    root.set("xmlns", NAMESPACE + message_type)
    root.set("xmlns:xsi", XSI_NAMESPACE)

    # Set the schema location for XML validation
    schema_location = f"{NAMESPACE}{message_type} {message_type}.xsd"
    root.set("xsi:schemaLocation", schema_location)

    return root
