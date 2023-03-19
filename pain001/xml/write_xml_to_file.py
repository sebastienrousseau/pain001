import xml.etree.ElementTree as ET

# Copyright (C) 2023 Sebastien Rousseau.
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

from xml.dom import minidom

# Write XML to file with pretty formatting (indentation)


def write_xml_to_file(xml_file_path, root):
    with open(xml_file_path, "w") as f:
        xml_string = ET.tostring(root, encoding="utf-8")
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_string = xml_declaration + xml_string.decode("utf-8")

        dom = minidom.parseString(xml_string)
        f.write(dom.toprettyxml())
