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

"""
This module includes functions for creating XML documents according to
different versions of the pain.001 schema as defined in ISO 20022. The
functions take a list of dictionaries containing the data to be added to
the XML document and a dictionary mapping the Data column names to the XML
element names. The functions return the root element of the XML tree.

For more information on the ISO 20022 pain.001 schema, refer to the
official ISO 20022 message definitions website at:

- [ISO 20022 Message Definitions](
https://www.iso20022.org/iso-20022-message-definitions)
"""

# Import the functions from the other modules
from pain001.xml.create_xml_element import create_xml_element


def create_common_elements(parent, row, mapping):
    """
    Create common elements "PmtInfId" and "PmtMtd" in the XML tree using
    data from the CSV or SQLite Data Files.

    Parameters
    ----------
    parent : xml.etree.ElementTree.Element
        Parent element in the XML tree.
    row : list
        List of strings, each string is a row of the Data file.
    mapping : dict
        Dictionary with the mapping between XML tags and Data columns.
    """
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ["PmtInfId", "PmtMtd"]:
            create_xml_element(parent, xml_tag, row[csv_column])
