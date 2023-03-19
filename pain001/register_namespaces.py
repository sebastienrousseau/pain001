import xml.etree.ElementTree as ET

# Register the namespace prefixes with the ElementTree module so that
# they are automatically added to the XML tags when the XML elements
# are created (XML tags and CSV columns mapping)


def register_namespaces():
    ET.register_namespace(
        "", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
    )
    ET.register_namespace(
        "xsi", "http://www.w3.org/2001/XMLSchema-instance"
    )
