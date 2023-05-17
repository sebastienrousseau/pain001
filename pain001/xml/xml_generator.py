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

import sys

# Import the XML libraries
import xml.etree.ElementTree as ET

# Import the functions from the other modules
from .create_root_element import create_root_element
from .generate_updated_xml_file_path import generate_updated_xml_file_path
from .generate_xml import create_xml_v3, create_xml_v9
from .validate_via_xsd import validate_via_xsd
from .write_xml_to_file import write_xml_to_file
from pain001.constants.constants import valid_xml_types


# XML generator function that creates the XML file from the CSV data
# and the mapping dictionary between XML tags and CSV columns names and
# writes it to a file in the same directory as the CSV file


def xml_generator(
        data,
        mapping,
        payment_initiation_message_type,
        xml_file_path,
        xsd_file_path
):
    # Create the root element and set its attributes
    root = create_root_element(payment_initiation_message_type)

    # Define a mapping between the XML types and the XML generators
    xml_generators = {
        "pain.001.001.03": create_xml_v3,
        "pain.001.001.09": create_xml_v9,
    }

    # Check if the provided payment_initiation_message_type exists in
    # the mapping
    if payment_initiation_message_type in xml_generators:
        # Get the corresponding XML generation function for the XML type
        xml_generator = xml_generators[payment_initiation_message_type]

        # Generate the XML file for the XML type and set its attributes
        xml_generator(root, data, mapping)
    else:
        # Handle the case when the payment_initiation_message_type is
        # not valid
        print(
            f"❌ Error: Invalid XML message type: {payment_initiation_message_type}")
        sys.exit(1)

    # Generate updated XML file path
    updated_xml_file_path = generate_updated_xml_file_path(
        xml_file_path,
        payment_initiation_message_type
    )

    # Write the updated XML tree to a file
    write_xml_to_file(updated_xml_file_path, root)

    # Validate the updated XML file against the XSD schema
    # is_valid = validate_via_xsd(
    #     updated_xml_file_path,
    #     xsd_file_path
    # )
    # if not is_valid:
    #     print("❌ Error: Invalid XML data.")
    #     sys.exit(1)
    # else:
    #     print(f"❯ XML located at {updated_xml_file_path} is valid.")
