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

import xml.etree.ElementTree as et


def create_xml_element(parent, tag, text=None, attributes=None):
    """
    Create and append an XML element with the specified tag, text, and
    attributes to a given parent element in the XML tree. The new element
    becomes a child of the parent element.

    Parameters
    ----------
    parent : xml.etree.ElementTree.Element
        The parent XML element to which the new element will be appended.
    tag : str
        The name of the XML tag for the new element.
    text : str, optional
        The text content to be inserted into the new XML element. Defaults to
        None.
    attributes : dict of {str: str}, optional
        A dictionary containing the attribute names and their corresponding
        values to be set in the new XML element. Defaults to None.

    Returns
    -------
    xml.etree.ElementTree.Element
        The newly created and appended XML element.
    """
    element = et.Element(tag)
    if text is not None:
        element.text = text
    if attributes is not None:
        for key, value in attributes.items():
            element.set(key, value)
    parent.append(element)
    return element
