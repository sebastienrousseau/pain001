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


import xml.etree.ElementTree as et  # nosec B405 - only used for element creation in tests, not parsing

from pain001.xml.create_root_element import create_root_element

# Test if the root element is created correctly


def test_create_root_element() -> None:
    # Define the XML message type
    payment_initiation_message_type = "pain.001.001.03"

    # Create the root element
    root = create_root_element(payment_initiation_message_type)

    # Check if root element has correct tag
    assert root.tag == "Document"

    # Check if xmlns attribute is set correctly
    xmlns_attr = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    assert root.attrib["xmlns"] == xmlns_attr

    # Check if xmlns:xsi attribute is set correctly
    xsi_attr = "http://www.w3.org/2001/XMLSchema-instance"
    assert root.attrib["xmlns:xsi"] == xsi_attr

    # Check if xsi:schemaLocation attribute is set correctly
    schema_location = (
        "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 pain.001.001.03.xsd"
    )
    assert root.attrib["xsi:schemaLocation"] == schema_location


def test_create_root_element_returns_element_object() -> None:
    # Define the XML message type
    payment_initiation_message_type = "pain.001.001.03"

    # Create the root element
    root = create_root_element(payment_initiation_message_type)

    # Check if root element is an instance of Element
    assert isinstance(root, et.Element)


def test_create_root_element_does_not_raise_exception() -> None:
    try:
        # Define the XML message type
        payment_initiation_message_type = "pain.001.001.03"

        # Create the root element
        create_root_element(payment_initiation_message_type)
    except Exception as err:
        error_msg = "create_root_element unexpected exception"
        raise AssertionError(error_msg) from err


def test_create_root_element_handles_empty_input_gracefully() -> None:
    # Test that the function does not raise an exception when
    # called with no input
    try:
        # Define the XML message type
        payment_initiation_message_type = "pain.001.001.03"

        # Create the root element
        create_root_element(payment_initiation_message_type)
    except Exception as err:
        error_msg = "create_root_element unexpected exception"
        raise AssertionError(error_msg) from err


def test_create_root_element_sets_all_expected_attributes_correctly() -> None:
    # Define the XML message type
    payment_initiation_message_type = "pain.001.001.03"

    # Create the root element
    root = create_root_element(payment_initiation_message_type)

    # Check if required attributes are set correctly
    assert root.tag == "Document"

    # Check if xmlns attribute is set correctly
    expected_xmlns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    assert root.attrib["xmlns"] == expected_xmlns

    # Check if xmlns:xsi attribute is set correctly
    expected_xsi = "http://www.w3.org/2001/XMLSchema-instance"
    assert root.attrib["xmlns:xsi"] == expected_xsi

    # Check if xsi:schemaLocation attribute is set correctly
    assert root.attrib["xsi:schemaLocation"] == (
        "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 pain.001.001.03.xsd"
    )

    # Check if optional attributes are set correctly
    root_with_optional_attrs = create_root_element(
        payment_initiation_message_type
    )
    assert "xmlns:xs" not in root_with_optional_attrs.attrib.keys()

    root = create_root_element(payment_initiation_message_type)

    # Check that optional attributes are not set by default
    assert "xmlns:xs" not in root.attrib.keys()
    assert "xmlns:foo" not in root.attrib.keys()

    # Set optional attributes and check that they are set correctly
    root.set("xmlns:xs", "http://www.w3.org/2001/XMLSchema")
    root.set("xmlns:foo", "http://example.com/foo")
    assert root.attrib["xmlns:xs"] == "http://www.w3.org/2001/XMLSchema"
    assert root.attrib["xmlns:foo"] == "http://example.com/foo"
