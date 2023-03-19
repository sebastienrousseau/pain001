import xml.etree.ElementTree as ET

# Create an XML element with the specified tag, text, and attributes,
# and append it to the given parent element (XML tags and CSV columns
# mapping)


def create_xml_element(parent, tag, text=None, attributes=None):
    """
    Create an XML element with the specified tag, text, and
    attributes, and append it to the given parent element.

    Args:
        parent (Element): The parent element to append the new element
        to.
        tag (str): The tag name of the new element.
        text (str, optional): The text content of the new element.
        attributes (dict, optional): A dictionary of attribute names
        and values for the new element.

    Returns:
        Element: The created XML element.
    """
    element = ET.Element(tag)
    if text is not None:
        element.text = text
    if attributes is not None:
        for key, value in attributes.items():
            element.set(key, value)
    parent.append(element)
    return element
