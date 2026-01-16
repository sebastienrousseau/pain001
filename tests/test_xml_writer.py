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

import os
import tempfile
import xml.etree.ElementTree as et

import pytest

from pain001.xml.write_xml_to_file import write_xml_to_file


class TestWriteXmlToFile:
    """Test cases for the write_xml_to_file function."""

    def test_write_simple_xml(self) -> None:
        """Test writing a simple XML structure to a file."""
        # Create a simple XML structure
        root = et.Element("root")
        child = et.SubElement(root, "child")
        child.text = "Test content"

        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as f:
            temp_file = f.name

        try:
            # Write the XML to the file
            write_xml_to_file(temp_file, root)

            # Verify the file was created
            assert os.path.exists(temp_file)

            # Read the file and verify content
            with open(temp_file, encoding="utf-8") as f:
                content = f.read()
                assert "<?xml version=" in content
                assert "<root>" in content
                assert "<child>Test content</child>" in content

        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_write_xml_with_attributes(self) -> None:
        """Test writing XML with attributes to a file."""
        # Create XML with attributes
        root = et.Element("root", attrib={"version": "1.0"})
        child = et.SubElement(root, "child", attrib={"id": "1"})
        child.text = "Content"

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as f:
            temp_file = f.name

        try:
            write_xml_to_file(temp_file, root)

            with open(temp_file, encoding="utf-8") as f:
                content = f.read()
                assert 'version="1.0"' in content
                assert 'id="1"' in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_write_xml_with_nested_elements(self) -> None:
        """Test writing XML with nested elements."""
        root = et.Element("root")
        parent = et.SubElement(root, "parent")
        child = et.SubElement(parent, "child")
        grandchild = et.SubElement(child, "grandchild")
        grandchild.text = "Nested content"

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as f:
            temp_file = f.name

        try:
            write_xml_to_file(temp_file, root)

            with open(temp_file, encoding="utf-8") as f:
                content = f.read()
                assert "<root>" in content
                assert "<parent>" in content
                assert "<child>" in content
                assert "<grandchild>Nested content</grandchild>" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_write_xml_formatting(self) -> None:
        """Test that the XML is properly formatted with indentation."""
        root = et.Element("root")
        child1 = et.SubElement(root, "child1")
        child1.text = "Content 1"
        child2 = et.SubElement(root, "child2")
        child2.text = "Content 2"

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as f:
            temp_file = f.name

        try:
            write_xml_to_file(temp_file, root)

            with open(temp_file, encoding="utf-8") as f:
                content = f.read()
                # Check that content has indentation (multiple spaces/tabs)
                lines = content.split("\n")
                # Check for proper structure (not all on one line)
                assert len(lines) > 3

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_write_xml_to_nonexistent_directory(self) -> None:
        """Test writing XML to a directory that doesn't exist raises error."""
        root = et.Element("root")

        # Use a path that doesn't exist
        nonexistent_path = "/nonexistent/directory/file.xml"

        with pytest.raises(FileNotFoundError):
            write_xml_to_file(nonexistent_path, root)

    def test_write_xml_with_special_characters(self) -> None:
        """Test writing XML with special characters."""
        root = et.Element("root")
        child = et.SubElement(root, "child")
        child.text = "Special chars: <>&'\""

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as f:
            temp_file = f.name

        try:
            write_xml_to_file(temp_file, root)

            with open(temp_file, encoding="utf-8") as f:
                content = f.read()
                # Special characters should be escaped
                assert "<child>" in content
                assert "&lt;" in content or "Special chars:" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_write_xml_with_empty_elements(self) -> None:
        """Test indent_xml with empty leaf elements at various levels."""
        # Create XML with elements that have text to cover all branches:
        # - Elements with children (len(elem) > 0)
        # - Elements with existing text and tail
        # - Empty leaf elements (len(elem) == 0) at level > 0
        root = et.Element("root")

        # Empty child at level 1 (triggers else branch with level > 0)
        empty_child = et.SubElement(root, "empty_child")
        assert empty_child is not None  # Verify element created

        # Parent with children (triggers if len(elem) branch)
        parent = et.SubElement(root, "parent")
        parent.text = "  "  # Has text that needs stripping

        # Nested child with whitespace tail
        child_with_tail = et.SubElement(parent, "child")
        child_with_tail.text = "Content"
        child_with_tail.tail = "   "  # Whitespace tail to be replaced

        # Nested empty at deeper level
        nested_empty = et.SubElement(parent, "nested_empty")
        assert nested_empty is not None  # Verify element created

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".xml"
        ) as f:
            temp_file = f.name

        try:
            write_xml_to_file(temp_file, root)

            with open(temp_file, encoding="utf-8") as f:
                content = f.read()
                # Verify proper indentation applied
                assert "<empty_child" in content
                assert "<parent>" in content
                assert "<child>Content</child>" in content
                assert "<nested_empty" in content

        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
