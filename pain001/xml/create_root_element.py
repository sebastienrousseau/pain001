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

import xml.etree.ElementTree as ET

# Create the root element and set its attributes (XML tags and CSV
# columns mapping)


def create_root_element():
    root = ET.Element("Document")
    root.set("xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    schema_location = (
        "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 " "pain.001.001.03.xsd"
    )
    root.set("xsi:schemaLocation", schema_location)

    for elem in root.iter():
        elem.tag = elem.tag.split("}", 1)[-1]

    return root