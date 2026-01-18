# Copyright (C) 2023-2026 Sebastien Rousseau.
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
The pain001.xml package provides functionality for generating, validating,
and manipulating ISO 20022 XML payment files.
"""

from pain001.xml.generate_xml import generate_xml
from pain001.xml.validate_via_xsd import (
    validate_via_xsd,
    validate_xml_string_via_xsd,
)
from pain001.xml.write_xml_to_file import write_xml_to_file
from pain001.xml.xml_to_string import xml_to_string

__all__ = [
    "generate_xml",
    "xml_to_string",
    "validate_via_xsd",
    "validate_xml_string_via_xsd",
    "write_xml_to_file",
]
