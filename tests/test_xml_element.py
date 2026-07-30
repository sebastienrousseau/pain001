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


import unittest
import xml.etree.ElementTree as et  # nosec B405 - only used for element creation in tests, not parsing

from pain001.xml.create_xml_element import create_xml_element

# Test if the XML element is created correctly


class TestCreateXmlElement(unittest.TestCase):
    def test_create_element_with_tag_only(self) -> None:
        """
        Test if the XML element is created correctly with a tag only.
        """
        root = et.Element("root")
        elem = create_xml_element(root, "test")
        self.assertEqual(elem.tag, "test")
        self.assertIsNone(elem.text)
        self.assertEqual(root.find("test"), elem)

    def test_create_element_with_tag_and_text(self) -> None:
        """
        Test if the XML element is created correctly with a tag and text.
        """
        root = et.Element("root")
        elem = create_xml_element(root, "test", text="Hello, world!")
        self.assertEqual(elem.tag, "test")
        self.assertEqual(elem.text, "Hello, world!")
        self.assertEqual(root.find("test"), elem)

    def test_create_element_with_tag_and_attributes(self) -> None:
        """
        Test if the XML element is created correctly with a tag and attributes.
        """
        root = et.Element("root")
        attributes = {"attr1": "value1", "attr2": "value2"}
        elem = create_xml_element(root, "test", attributes=attributes)
        self.assertEqual(elem.tag, "test")
        self.assertIsNone(elem.text)
        self.assertEqual(elem.attrib, attributes)
        self.assertEqual(root.find("test"), elem)

    def test_create_element_with_tag_text_and_attributes(self) -> None:
        """
        Test if the XML element is created correctly with a tag, text and
        attributes.
        """
        root = et.Element("root")
        attributes = {"attr1": "value1", "attr2": "value2"}
        elem = create_xml_element(
            root, "test", text="Hello, world!", attributes=attributes
        )
        self.assertEqual(elem.tag, "test")
        self.assertEqual(elem.text, "Hello, world!")
        self.assertEqual(elem.attrib, attributes)
        self.assertEqual(root.find("test"), elem)


if __name__ == "__main__":
    unittest.main()
