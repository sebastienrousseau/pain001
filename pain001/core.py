# Copyright (C) 2023 Sebastian Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import csv
import os
import sys
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom


def main(xml_file_path, csv_file_path):
    """This function, when called, generates a Customer-to-Bank Credit
    Transfer payload in a pain.001.001.03 format from a CSV file.

    Executes a command-line interface for the Pain001 library. The first
    argument is the path of the XML template file. The second argument
    is the path of the CSV file containing the payment data.

    Args:
        xml_file_path (str): The path of the XML template file.
        csv_file_path (str): The path of the CSV file containing the
        payment data.

    Returns:
        The generated XML file in the pain.001.001.03 format with the
        payment data.

    Raises:
        FileNotFoundError: If the XML template file does not exist.
        FileNotFoundError: If the CSV file does not exist.
    """

    # Define mapping dictionary between XML element tags and CSV column names
    mapping = {
        'MsgId': 'id',
        'CreDtTm': 'date',
        'NbOfTxs': 'nb_of_txs',
        'Nm': 'initiator_name',
    }

    # Load CSV data into a list of dictionaries
    data = []
    with open(csv_file_path, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            data.append(row)

    # Print out CSV data for debugging
    print(f"CSV data: {data}")

    root = ET.Element('Document', nsmap={
        None: 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    })

    root.set('xmlns', 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('xsi:schemaLocation',
             'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 pain.001.001.03.xsd')

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element('CstmrCdtTrfInitn')
    root.append(cstmr_cdt_trf_initn_element)

    # Create new "GrpHdr" elements in the XML tree using data from the CSV file
    for row in data:
        GrpHdr_element = ET.Element('GrpHdr')
        for tag, column_name in mapping.items():
            if '/' in tag:
                tag, sub_tag = tag.split('/')
                if tag == 'InitgPty':
                    if column_name in row:
                        InitgPty_element = ET.Element('InitgPty')
                        child_element = ET.Element(sub_tag)
                        child_element.text = row[column_name]
                        InitgPty_element.append(child_element)
                        GrpHdr_element.append(InitgPty_element)
            else:
                child_element = ET.Element(tag)
                child_element.text = row[column_name]
                if tag == 'Nm' and 'InitgPty' not in mapping:
                    # Wrap the Initiator Name with the InitgPty tag
                    InitgPty_element = ET.Element('InitgPty')
                    InitgPty_element.append(child_element)
                    GrpHdr_element.append(InitgPty_element)
                else:
                    GrpHdr_element.append(child_element)
        cstmr_cdt_trf_initn_element.append(GrpHdr_element)

        # Create new "PmtInf" elements in the XML tree using data from the CSV file
        PmtInf_element = ET.Element('PmtInf')
        for tag, column_name in mapping.items():
            if '/' in tag:
                tag, sub_tag = tag.split('/')
                if tag == 'PmtTpInf':
                    if column_name in row:
                        PmtTpInf_element = ET.Element('PmtTpInf')
                        child_element = ET.Element(sub_tag)
                        child_element.text = row[column_name]
                        PmtTpInf_element.append(child_element)
                        PmtInf_element.append(PmtTpInf_element)
            else:
                child_element = ET.Element(tag)
                child_element.text = row[column_name]
                if tag == 'Nm' and 'PmtTpInf' not in mapping:
                    # Wrap the Payment Type with the PmtTpInf tag
                    PmtTpInf_element = ET.Element('PmtTpInf')
                    PmtTpInf_element.append(child_element)
                    PmtInf_element.append(PmtTpInf_element)
                else:
                    PmtInf_element.append(child_element)
        cstmr_cdt_trf_initn_element.append(PmtInf_element)


    # Write the updated XML tree to a file
    updated_xml_file_path = os.path.splitext(
        xml_file_path)[0] + '_updated.xml'
    with open(updated_xml_file_path, 'w') as f:
        xml_string = ET.tostring(root, encoding='utf-8')
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + \
            xml_string.decode('utf-8')
        dom = minidom.parseString(xml_string)
        f.write(dom.toprettyxml())


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python Pain001.py <xml_file_path> <csv_file_path>')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
