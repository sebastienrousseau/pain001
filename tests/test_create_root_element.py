from pain001.create_root_element import create_root_element

# Test if the root element is created correctly


def test_create_root_element():
    root = create_root_element()

    # Check if root element has correct tag
    assert root.tag == 'Document'

    # Check if xmlns attribute is set correctly
    xmlns_attr = 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'
    assert root.attrib['xmlns'] == xmlns_attr

    # Check if xmlns:xsi attribute is set correctly
    xsi_attr = 'http://www.w3.org/2001/XMLSchema-instance'
    assert root.attrib['xmlns:xsi'] == xsi_attr

    # Check if xsi:schemaLocation attribute is set correctly
    schema_location = (
        'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 '
        'pain.001.001.03.xsd'
    )
    assert root.attrib['xsi:schemaLocation'] == schema_location
