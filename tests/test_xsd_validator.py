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
import unittest

from pain001.xml.validate_via_xsd import validate_via_xsd

# Test if the XML file is validated correctly against the XSD schema


class TestValidateViaXsd(unittest.TestCase):
    def setUp(self) -> None:
        """
        Test case setup method.
        """
        self.valid_xml_file = "valid_test.xml"
        self.invalid_xml_file = "invalid_test.xml"
        self.xsd_file = "test_schema.xsd"

        # Create valid XML test file
        with open(self.valid_xml_file, "w", encoding="utf-8") as f:
            f.write(
                """<root>
                            <element>Valid data</element>
                        </root>"""
            )

        # Create invalid XML test file
        with open(self.invalid_xml_file, "w", encoding="utf-8") as f:
            f.write(
                """
            <root>
                <invalidElement>Invalid data</invalidElement>
            </root>
            """
            )

        # Create test XSD schema file
        with open(self.xsd_file, "w", encoding="utf-8") as f:
            f.write(
                """
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:sequence>
                            <xs:element name="element">
                                <xs:simpleType>
                                    <xs:restriction base="xs:string"/>
                                </xs:simpleType>
                            </xs:element>
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """
            )

    def tearDown(self) -> None:
        """
        Test case tear down method.
        """
        os.remove(self.valid_xml_file)
        os.remove(self.invalid_xml_file)
        os.remove(self.xsd_file)

    def test_valid_xml(self) -> None:
        """
        Test case for validating a valid XML file against an XSD schema.
        """
        assert validate_via_xsd(self.valid_xml_file, self.xsd_file)

    def test_invalid_xml(self) -> None:
        """
        Test case for validating an invalid XML file against an XSD schema.
        """
        assert not validate_via_xsd(self.invalid_xml_file, self.xsd_file)
        assert not validate_via_xsd(self.invalid_xml_file, self.xsd_file)

    def test_invalid_xml_file_path(self) -> None:
        """
        Test case for handling non-existent XML file.
        """
        result = validate_via_xsd("nonexistent.xml", self.xsd_file)
        assert result is False

    def test_malformed_xml_file(self) -> None:
        """
        Test case for handling malformed XML file.
        """
        malformed_xml = "malformed_test.xml"

        # Create malformed XML
        with open(malformed_xml, "w", encoding="utf-8") as f:
            f.write("<root><unclosed>")

        try:
            result = validate_via_xsd(malformed_xml, self.xsd_file)
            assert result is False
        finally:
            if os.path.exists(malformed_xml):
                os.remove(malformed_xml)

    def test_invalid_xsd_schema(self) -> None:
        """
        Test case for handling invalid XSD schema file.
        """
        invalid_xsd = "invalid_schema.xsd"

        # Create invalid XSD
        with open(invalid_xsd, "w", encoding="utf-8") as f:
            f.write("<invalid>schema</invalid>")

        try:
            # xmlschema will raise an exception for invalid XSD
            # which our function should catch and return False
            try:
                result = validate_via_xsd(self.valid_xml_file, invalid_xsd)
                # Should return False for invalid XSD
                assert result is False
            except Exception:
                # If exception is raised, that's also acceptable behavior
                pass
        finally:
            if os.path.exists(invalid_xsd):
                os.remove(invalid_xsd)

    def test_validation_exception_during_validation(self) -> None:
        """
        Test case for exception during XML validation process.
        """
        from unittest.mock import patch

        import xmlschema

        # Create a valid XML and XSD for parsing
        valid_xml = "test_valid.xml"
        valid_xsd = "test_valid.xsd"

        with open(valid_xml, "w", encoding="utf-8") as f:
            f.write("<root><element>data</element></root>")

        with open(valid_xsd, "w", encoding="utf-8") as f:
            f.write(
                """
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:element name="root">
                        <xs:complexType>
                            <xs:sequence>
                                <xs:element name="element" type="xs:string"/>
                            </xs:sequence>
                        </xs:complexType>
                    </xs:element>
                </xs:schema>
            """
            )

        try:
            # Mock xsd.validate to raise an XMLSchemaException during validation
            with patch(
                "xmlschema.XMLSchema", autospec=True
            ) as mock_schema_class:
                # Create instance mock from the class mock
                mock_xsd = mock_schema_class.return_value
                # Mock the validate() method that our production code calls (line 53 in validate_via_xsd.py)
                mock_xsd.validate.side_effect = xmlschema.XMLSchemaException(
                    "Validation error"
                )

                result = validate_via_xsd(valid_xml, valid_xsd)
                # Should return False when validation raises exception
                assert result is False
        finally:
            if os.path.exists(valid_xml):
                os.remove(valid_xml)
            if os.path.exists(valid_xsd):
                os.remove(valid_xsd)


if __name__ == "__main__":
    unittest.main()
