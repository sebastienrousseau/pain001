import xmlschema
import xml.etree.ElementTree as ET

# Validate XML file against XSD schema using xmlschema package
# (https://pypi.org/project/xmlschema/) and ElementTree package
# (https://docs.python.org/3/library/xml.etree.elementtree.html)


def validate_via_xsd(xml_file_path, xsd_file_path):
    # Load XML and XSD files
    xml_tree = ET.parse(xml_file_path)
    xsd = xmlschema.XMLSchema(xsd_file_path)

    # Validate XML file against XSD schema
    is_valid = xsd.is_valid(xml_tree)

    return is_valid
