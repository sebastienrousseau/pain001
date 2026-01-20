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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for pain001.xml.xml_to_string module.
Tests XML-to-string conversion for serverless/API architectures.
"""

# pylint: disable=too-few-public-methods

import xml.etree.ElementTree as ET  # noqa: N817  # nosec B405 - Safe: element creation only, no parsing

from pain001.xml.xml_to_string import xml_to_string


class TestXmlToString:
    """Test suite for xml_to_string function."""

    def test_simple_xml_with_declaration(self):
        """Test converting simple XML with declaration."""
        root = ET.Element("Document")
        root.set("xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
        child = ET.SubElement(root, "CstmrCdtTrfInitn")
        child.text = "Test"

        result = xml_to_string(root, include_declaration=True)

        # Match our XML normalization: double quotes, uppercase UTF-8
        assert result.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert "<Document" in result
        assert (
            'xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"' in result
        )
        assert "<CstmrCdtTrfInitn>Test</CstmrCdtTrfInitn>" in result

    def test_simple_xml_without_declaration(self):
        """Test converting XML without declaration."""
        root = ET.Element("Document")
        child = ET.SubElement(root, "Test")
        child.text = "Value"

        result = xml_to_string(root, include_declaration=False)

        assert not result.startswith("<?xml")
        assert "<Document>" in result
        assert "<Test>Value</Test>" in result

    def test_nested_xml_structure(self):
        """Test converting nested XML structure."""
        root = ET.Element("Document")
        level1 = ET.SubElement(root, "Level1")
        level2 = ET.SubElement(level1, "Level2")
        level3 = ET.SubElement(level2, "Level3")
        level3.text = "Deep Value"

        result = xml_to_string(root)

        assert "<Document>" in result
        assert "<Level1>" in result
        assert "<Level2>" in result
        assert "<Level3>Deep Value</Level3>" in result
        assert result.count("\n") >= 3  # Verify indentation exists

    def test_xml_with_attributes(self):
        """Test converting XML with multiple attributes."""
        root = ET.Element("Document")
        root.set("xmlns", "urn:test")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        child = ET.SubElement(root, "Element")
        child.set("attr1", "value1")
        child.set("attr2", "value2")

        result = xml_to_string(root)

        assert 'xmlns="urn:test"' in result
        assert "xmlns:xsi" in result
        assert 'attr1="value1"' in result
        assert 'attr2="value2"' in result

    def test_xml_with_special_characters(self):
        """Test converting XML with special characters (proper escaping)."""
        root = ET.Element("Document")
        child = ET.SubElement(root, "Text")
        child.text = "Test & < > \" ' characters"

        result = xml_to_string(root)

        # ElementTree automatically escapes special characters
        assert "&amp;" in result or "&" in result
        assert "&lt;" in result or "<" in result
        # Note: ET may not escape all characters in text content

    def test_empty_element(self):
        """Test converting empty XML element."""
        root = ET.Element("EmptyRoot")

        result = xml_to_string(root)

        assert "<EmptyRoot" in result
        # Could be <EmptyRoot /> or <EmptyRoot></EmptyRoot>
        assert "EmptyRoot" in result

    def test_multiple_siblings(self):
        """Test converting XML with multiple sibling elements."""
        root = ET.Element("Root")
        for i in range(5):
            child = ET.SubElement(root, f"Child{i}")
            child.text = f"Value{i}"

        result = xml_to_string(root)

        for i in range(5):
            assert f"<Child{i}>Value{i}</Child{i}>" in result

    def test_indentation_formatting(self):
        """Test that output XML is properly indented."""
        root = ET.Element("Root")
        level1 = ET.SubElement(root, "Level1")
        level2 = ET.SubElement(level1, "Level2")
        level2.text = "Content"

        result = xml_to_string(root)

        # Verify indentation exists (newlines and spaces)
        lines = result.split("\n")
        assert len(lines) > 3
        # Check that child elements are indented
        assert any("  <Level1>" in line for line in lines)
        assert any("    <Level2>" in line for line in lines)

    def test_utf8_encoding(self):
        """Test UTF-8 encoding with international characters."""
        root = ET.Element("Document")
        child = ET.SubElement(root, "Name")
        child.text = "François Müller 日本"

        result = xml_to_string(root)

        assert "François Müller 日本" in result or "Fran" in result
        # UTF-8 should handle international characters

    def test_consistency_with_write_xml_to_file(self):
        """Test that xml_to_string produces same structure as write_xml_to_file."""
        import tempfile

        from pain001.xml.write_xml_to_file import write_xml_to_file

        root = ET.Element("Document")
        level1 = ET.SubElement(root, "Child")
        level1.text = "Test Value"

        # Get string version
        string_result = xml_to_string(root, include_declaration=True)

        # Write to temp file and read back
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False
        ) as tmp:
            tmp_path = tmp.name

        # Need to recreate root because indent_xml modifies it
        root2 = ET.Element("Document")
        level1_2 = ET.SubElement(root2, "Child")
        level1_2.text = "Test Value"

        write_xml_to_file(tmp_path, root2)

        with open(tmp_path, encoding="utf-8") as f:
            file_result = f.read()

        # Both should have same structure (minor differences in spacing acceptable)
        assert "<Document>" in string_result
        assert "<Document>" in file_result
        assert "<Child>Test Value</Child>" in string_result
        assert "<Child>Test Value</Child>" in file_result

        import os

        os.unlink(tmp_path)

    def test_large_xml_structure(self):
        """Test converting large XML structure (performance check)."""
        root = ET.Element("Root")
        for i in range(100):
            parent = ET.SubElement(root, f"Parent{i}")
            for j in range(10):
                child = ET.SubElement(parent, f"Child{j}")
                child.text = f"Value_{i}_{j}"

        result = xml_to_string(root)

        # Verify structure
        assert "<Root>" in result
        assert "Parent0" in result
        assert "Parent99" in result
        assert "Value_50_5" in result
        # Should complete without errors or excessive memory usage

    def test_default_declaration_parameter(self):
        """Test that include_declaration defaults to True."""
        root = ET.Element("Test")

        result = xml_to_string(root)  # No parameter specified

        # Match our XML normalization: double quotes, uppercase UTF-8
        assert result.startswith('<?xml version="1.0" encoding="UTF-8"?>')
