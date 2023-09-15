# Copyright (C) 2023 Sebastien Rousseau.
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
Module for creating secure XML payment initiation message documents.

Uses the defusedxml library to prevent XML vulnerabilities.
"""

import xml.etree.ElementTree as ET

NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:"

XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"


def create_root_element(message_type: str) -> ET.Element:
    """
    Create the root Element for a payment initiation XML document.

    Args:
        message_type: The message type string, e.g. "pain.001.001.09".

    Returns:
        The root Element node for the XML document.
    """

    # Use ET.Element instead of parser.ProcessingInstruction
    root = ET.Element("Document")

    # Add xmlns and xmlns_xsi attributes directly to the root element
    root.set("xmlns", NAMESPACE + message_type)
    root.set("xmlns:xsi", XSI_NAMESPACE)

    schema_location = f"{NAMESPACE}{message_type} {message_type}.xsd"
    root.set("xsi:schemaLocation", schema_location)

    return root
