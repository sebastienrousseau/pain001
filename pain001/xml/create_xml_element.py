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

"""Helper for creating XML child elements."""

import xml.etree.ElementTree as et  # nosec B405


def create_xml_element(
    parent: et.Element,
    tag: str,
    text: str | None = None,
    attributes: dict[str, str] | None = None,
) -> et.Element:
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
