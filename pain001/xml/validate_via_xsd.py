import xmlschema

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
