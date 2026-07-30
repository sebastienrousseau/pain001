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


from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)

# Test if the updated XML file path is generated correctly


def test_generate_updated_xml_file_path() -> None:
    # Test with a file path that has an extension
    payment_initiation_message_type = "pain.001.001.03"
    xml_file_path = "pain001/test_fixtures/template.xml"
    expected_output = "pain001/test_fixtures/pain.001.001.03.xml"
    assert (
        generate_updated_xml_file_path(
            xml_file_path, payment_initiation_message_type
        )
        == expected_output
    )
