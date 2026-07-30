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

# Standard library imports

"""Derive the legacy template-relative output path for generated XML."""

import os

# Generate the path to the updated XML file based on the path to the
# original XML file


def generate_updated_xml_file_path(
    xml_file_path: str, payment_initiation_message_type: str
) -> str:
    """Generates the file path for an updated XML file.

    Given the original XML file path and payment message type, this function
    constructs the file path for an updated version of the XML file with
    the provided message type in the filename.

    Args:
        xml_file_path: The path to the original XML file.
        payment_initiation_message_type: The payment message type
            (e.g. 'pain.001.001.04').

    Returns:
        str: The file path to the updated XML file.

    """

    base_directory = os.path.dirname(xml_file_path)

    # Construct new file path
    new_file_name = payment_initiation_message_type + ".xml"
    new_file_path = os.path.join(base_directory, new_file_name)

    return new_file_path
