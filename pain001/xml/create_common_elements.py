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

"""
This module includes functions for creating XML documents in compliance with
different versions of the pain.001 schema as defined in ISO 20022. These
functions take a list of dictionaries containing the data to populate the XML
document, as well as a dictionary that maps the column names in the data to
the XML element names. The functions return the root element of the XML tree.

For more information on the ISO 20022 pain.001 schema, refer to the
official ISO 20022 message definitions website:

- <https://www.iso20022.org/iso-20022-message-definitions>
"""

# Import required modules
from pain001.xml.create_xml_element import create_xml_element


def create_common_elements(parent, row, mapping):
    """
    Creates common XML elements, specifically "PmtInfId" and "PmtMtd",
    in the XML tree. This function uses data from the input Data files, which
    could either be CSV or SQLite data files.

    Parameters
    ----------
    parent : xml.etree.ElementTree.Element
        The parent element in the XML tree where the new elements will be
        added.
    row : list of str
        A list of strings where each string represents a value from a single
        row in the Data file.
    mapping : dict of {str: str}
        A dictionary mapping XML tags to corresponding Data file column names.
        For example, if "PmtInfId" maps to "PaymentInfoID", the element
        "PmtInfId" will be created with the data from the "PaymentInfoID"
        column.

    Returns
    -------
    None
        This function modifies the XML tree in-place and does not return any
        value.
    """
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ["PmtInfId", "PmtMtd"]:
            create_xml_element(parent, xml_tag, row[csv_column])
