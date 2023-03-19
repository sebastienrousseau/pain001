import xml.etree.ElementTree as ET

# Create the root element and set its attributes (XML tags and CSV
# columns mapping)


def create_root_element():
    root = ET.Element("Document")
    root.set("xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    schema_location = (
        "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 "
        "pain.001.001.03.xsd"
    )
    root.set("xsi:schemaLocation", schema_location)

    for elem in root.iter():
        elem.tag = elem.tag.split("}", 1)[-1]

    return root
