import unittest
import xml.etree.ElementTree as ET
from pain001.xml.create_xml_element import create_xml_element

# Test if the XML element is created correctly


class TestCreateXmlElement(unittest.TestCase):
    def test_create_element_with_tag_only(self):
        """
        Test if the XML element is created correctly with a tag only.
        """
        root = ET.Element("root")
        elem = create_xml_element(root, "test")
        self.assertEqual(elem.tag, "test")
        self.assertIsNone(elem.text)
        self.assertEqual(root.find("test"), elem)

    def test_create_element_with_tag_and_text(self):
        """
        Test if the XML element is created correctly with a tag and text.
        """
        root = ET.Element("root")
        elem = create_xml_element(root, "test", text="Hello, world!")
        self.assertEqual(elem.tag, "test")
        self.assertEqual(elem.text, "Hello, world!")
        self.assertEqual(root.find("test"), elem)

    def test_create_element_with_tag_and_attributes(self):
        """
        Test if the XML element is created correctly with a tag and attributes.
        """
        root = ET.Element("root")
        attributes = {"attr1": "value1", "attr2": "value2"}
        elem = create_xml_element(root, "test", attributes=attributes)
        self.assertEqual(elem.tag, "test")
        self.assertIsNone(elem.text)
        self.assertEqual(elem.attrib, attributes)
        self.assertEqual(root.find("test"), elem)

    def test_create_element_with_tag_text_and_attributes(self):
        """
        Test if the XML element is created correctly with a tag, text and
        attributes.
        """
        root = ET.Element("root")
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
