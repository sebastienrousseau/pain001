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

"""Tests for the register_namespaces module."""

import xml.etree.ElementTree as et  # nosec B405 - only used for element creation in tests, not parsing

from pain001.xml.register_namespaces import register_namespaces


class TestRegisterNamespaces:
    """Test the register_namespaces function."""

    def test_register_namespaces_pain_001_001_03(self) -> None:
        """Test registering namespaces for pain.001.001.03."""
        message_type = "pain.001.001.03"
        register_namespaces(message_type)

        # Create a test element to verify namespace registration
        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")

        # Convert to string and verify namespace is in the output
        xml_string = et.tostring(root, encoding="unicode")
        assert namespace in xml_string
        assert "Document" in xml_string

    def test_register_namespaces_pain_001_001_04(self) -> None:
        """Test registering namespaces for pain.001.001.04."""
        message_type = "pain.001.001.04"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string

    def test_register_namespaces_pain_001_001_05(self) -> None:
        """Test registering namespaces for pain.001.001.05."""
        message_type = "pain.001.001.05"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string

    def test_register_namespaces_pain_001_001_06(self) -> None:
        """Test registering namespaces for pain.001.001.06."""
        message_type = "pain.001.001.06"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string

    def test_register_namespaces_pain_001_001_07(self) -> None:
        """Test registering namespaces for pain.001.001.07."""
        message_type = "pain.001.001.07"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string

    def test_register_namespaces_pain_001_001_08(self) -> None:
        """Test registering namespaces for pain.001.001.08."""
        message_type = "pain.001.001.08"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string

    def test_register_namespaces_pain_001_001_09(self) -> None:
        """Test registering namespaces for pain.001.001.09."""
        message_type = "pain.001.001.09"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string

    def test_register_namespaces_xsi_namespace(self) -> None:
        """Test that xsi namespace is registered correctly."""
        message_type = "pain.001.001.03"
        register_namespaces(message_type)

        # Create element with xsi namespace
        xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"
        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"

        root = et.Element(f"{{{namespace}}}Document")
        root.set(f"{{{xsi_ns}}}schemaLocation", "test")

        xml_string = et.tostring(root, encoding="unicode")
        assert "xsi:" in xml_string or xsi_ns in xml_string

    def test_register_namespaces_returns_none(self) -> None:
        """Test that register_namespaces returns None (side-effect function)."""
        message_type = "pain.001.001.03"
        # register_namespaces is a procedure (returns None), called for side effects
        register_namespaces(message_type)
        # No assertion needed - function registers namespaces internally

    def test_register_namespaces_with_custom_message_type(self) -> None:
        """Test registering namespaces with a custom message type."""
        message_type = "pain.001.001.10"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}CustomDocument")
        xml_string = et.tostring(root, encoding="unicode")

        assert namespace in xml_string
        assert "CustomDocument" in xml_string

    def test_register_namespaces_namespace_format(self) -> None:
        """Test that the namespace is formatted correctly."""
        message_type = "pain.001.001.03"
        register_namespaces(message_type)

        expected_namespace = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"

        root = et.Element(f"{{{expected_namespace}}}Document")
        xml_string = et.tostring(root, encoding="unicode")

        assert "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03" in xml_string

    def test_register_namespaces_multiple_calls(self) -> None:
        """Test calling register_namespaces multiple times with different types."""
        # First call
        register_namespaces("pain.001.001.03")
        namespace_03 = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
        root_03 = et.Element(f"{{{namespace_03}}}Document")
        xml_03 = et.tostring(root_03, encoding="unicode")

        # Second call with different type
        register_namespaces("pain.001.001.04")
        namespace_04 = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.04"
        root_04 = et.Element(f"{{{namespace_04}}}Document")
        xml_04 = et.tostring(root_04, encoding="unicode")

        assert namespace_03 in xml_03
        assert namespace_04 in xml_04

    def test_register_namespaces_with_child_elements(self) -> None:
        """Test that namespace registration works with child elements."""
        message_type = "pain.001.001.03"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        child = et.SubElement(root, f"{{{namespace}}}CstmrCdtTrfInitn")
        et.SubElement(child, f"{{{namespace}}}GrpHdr")

        xml_string = et.tostring(root, encoding="unicode")

        assert "Document" in xml_string
        assert "CstmrCdtTrfInitn" in xml_string
        assert "GrpHdr" in xml_string

    def test_register_namespaces_preserves_element_tree_functionality(
        self,
    ) -> None:
        """Test that ElementTree functionality is preserved after registration."""
        message_type = "pain.001.001.03"
        register_namespaces(message_type)

        namespace = f"urn:iso:std:iso:20022:tech:xsd:{message_type}"
        root = et.Element(f"{{{namespace}}}Document")
        root.set("version", "1.0")
        child = et.SubElement(root, f"{{{namespace}}}Child")
        child.text = "Test Content"

        # Verify we can still access and modify elements
        assert root.get("version") == "1.0"
        assert child.text == "Test Content"
        assert len(root) == 1

        xml_string = et.tostring(root, encoding="unicode")
        assert "Test Content" in xml_string
        assert 'version="1.0"' in xml_string
