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


import unittest
import os
from pain001.xml.validate_via_xsd import validate_via_xsd

# Test if the XML file is validated correctly against the XSD schema


class TestValidateViaXsd(unittest.TestCase):
    def setUp(self):
        """
        Test case setup method.
        """
        self.valid_xml_file = "valid_test.xml"
        self.invalid_xml_file = "invalid_test.xml"
        self.xsd_file = "test_schema.xsd"

        # Create valid XML test file
        with open(self.valid_xml_file, "w") as f:
            f.write(
                """<root>
                            <element>Valid data</element>
                        </root>"""
            )

        # Create invalid XML test file
        with open(self.invalid_xml_file, "w") as f:
            f.write(
                """
            <root>
                <invalidElement>Invalid data</invalidElement>
            </root>
            """
            )

        # Create test XSD schema file
        with open(self.xsd_file, "w") as f:
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

    def tearDown(self):
        """
        Test case tear down method.
        """
        os.remove(self.valid_xml_file)
        os.remove(self.invalid_xml_file)
        os.remove(self.xsd_file)

    def test_valid_xml(self):
        """
        Test case for validating a valid XML file against an XSD schema.
        """
        assert validate_via_xsd(self.valid_xml_file, self.xsd_file)

    def test_invalid_xml(self):
        """
        Test case for validating an invalid XML file against an XSD schema.
        """
        assert not validate_via_xsd(self.invalid_xml_file, self.xsd_file)
        assert not validate_via_xsd(self.invalid_xml_file, self.xsd_file)
