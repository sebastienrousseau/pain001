import xmlschema

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


def validate_via_xsd(xml_file_path, xsd_file_path):
    """
    Validates an XML file against an XSD schema.

    Args:
        xml_file_path (str): Path to the XML file to validate.
        xsd_file_path (str): Path to the XSD schema file.

    Returns:
        bool: True if the XML file is valid, False otherwise.
    """

    # Load XML file into an ElementTree object.
    try:
        xml_tree = et.parse(xml_file_path)
    except Exception as e:
        print(f"Error: {e}")
        return False

    # Load XSD schema into an XMLSchema object.
    xsd = xmlschema.XMLSchema(xsd_file_path)

    # Validate XML file against XSD schema.
    try:
        is_valid = xsd.is_valid(xml_tree)
    except Exception as e:
        print(f"Error: {e}")
        return False

    # Return True if XML file is valid, False otherwise.
    return is_valid
