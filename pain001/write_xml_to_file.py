import xml.etree.ElementTree as ET
from xml.dom import minidom

# Write XML to file with pretty formatting (indentation)


def write_xml_to_file(xml_file_path, root):
    with open(xml_file_path, "w") as f:
        xml_string = ET.tostring(root, encoding="utf-8")
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + \
            xml_string.decode("utf-8")
        dom = minidom.parseString(xml_string)
        f.write(dom.toprettyxml())
