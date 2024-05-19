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

"""
This module contains a utility function for writing XML content to a file.
The XML content is pretty-formatted with proper indentation for better
readability.
"""

import xml.etree.ElementTree as et
from defusedxml.minidom import parseString


def write_xml_to_file(xml_file_path, root):
    """
    Write the XML tree to a file, with pretty formatting (indentation).

    Parameters
    ----------
    xml_file_path : str
        The file path where the XML content will be written.
    root : xml.etree.ElementTree.Element
        The root element of the XML tree.

    Returns
    -------
    None
        The function writes the XML content to a file and does not return any
        value.
    """

    with open(xml_file_path, "w") as f:
        xml_string = et.tostring(root, encoding="utf-8")
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_string = xml_declaration + xml_string.decode("utf-8")

        # Pretty-format the XML string using minidom
        dom = parseString(xml_string)
        f.write(dom.toprettyxml())
