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


from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)

# Test if the updated XML file path is generated correctly


def test_generate_updated_xml_file_path():
    # Test with a file path that has an extension
    xml_file_path = "tests/data/template.xml"
    payment_initiation_message_type = "pain.001.001.03"
    expected_output = "tests/data/pain.001.001.03.xml"
    assert (
        generate_updated_xml_file_path(
            xml_file_path, payment_initiation_message_type
        )
        == expected_output
    )
