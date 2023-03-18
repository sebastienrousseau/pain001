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

# Import required libraries
import csv
import os
import sys
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom


def validate_csv_data(data):
    """Validate the CSV data before processing it.

    Args:
        data (list): A list of dictionaries containing the CSV data.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    required_columns = {
        'id': int,
        'date': str,
        'nb_of_txs': int,
        'initiator_name': str,
        'payment_information_id': str,
        'payment_method': str,
        'batch_booking': bool,
        'control_sum': int,
        'service_level_code': str,
        'requested_execution_date': str,
        'debtor_name': str,
        'debtor_account_IBAN': str,
        'debtor_agent_BIC': str,
        'forwarding_agent_BIC': str,
        'charge_bearer': str,
        'payment_id': str,
        'payment_amount': float,
        'currency': str,
        'creditor_agent_BIC': str,
        'creditor_name': str,
        'creditor_account_IBAN': str,
        'remittance_information': str
    }

    for row in data:
        for column, data_type in required_columns.items():
            value = row.get(column)
            if value is None or value.strip() == '':
                print(
                    f"Error: Missing value for column '{column}' in row: {row}")
                return False

            try:
                if data_type == int:
                    int(value)
                elif data_type == float:
                    float(value)
                elif data_type == bool:
                    if value.lower() not in ['true', 'false']:
                        raise ValueError
                else:
                    str(value)
            except ValueError:
                print(
                    f"Error: Invalid data type for column '{column}', expected {data_type.__name__} in row: {row}")
                return False

    return True


def create_xml_element(parent, tag, text=None, attributes=None):
    """Create an XML element with the specified tag, text, and attributes, and
    append it to the given parent element.

    Args:
        parent (Element): The parent element to append the new element to.
        tag (str): The tag name of the new element.
        text (str, optional): The text content of the new element.
        attributes (dict, optional): A dictionary of attribute names and
        values for the new element.

    Returns:
        Element: The created XML element.
    """
    element = ET.Element(tag)
    if text is not None:
        element.text = text
    if attributes is not None:
        for key, value in attributes.items():
            element.set(key, value)
    parent.append(element)
    return element


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
        'PmtInfId': 'payment_information_id',
        'PmtMtd': 'payment_method',
    }

    # Load CSV data into a list of dictionaries
    data = []
    with open(csv_file_path, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            data.append(row)

    # Validate the CSV data
    if not validate_csv_data(data):
        print("Error: Invalid CSV data.")
        sys.exit(1)

    # Print out CSV data for debugging
    print(f"CSV data: {data}")

    # Register the namespace prefixes
    ET.register_namespace('', 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03')
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

    # Create the root element and set its attributes
    root = ET.Element('Document')
    root.set('xmlns', 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('xsi:schemaLocation',
             'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03 pain.001.001.03.xsd')

    # Remove the namespace prefix from the Document element
    for elem in root.iter():
        elem.tag = elem.tag.split('}', 1)[-1]

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element('CstmrCdtTrfInitn')
    root.append(cstmr_cdt_trf_initn_element)

    # Create GrpHdr element and append it to CstmrCdtTrfInitn
    GrpHdr_element = ET.Element('GrpHdr')
    cstmr_cdt_trf_initn_element.append(GrpHdr_element)

    # Add the MsgId, CreDtTm, and NbOfTxs elements to the GrpHdr element
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ['MsgId', 'CreDtTm', 'NbOfTxs']:
            create_xml_element(GrpHdr_element, xml_tag, data[0][csv_column])

    # Create new "InitgPty" element in the XML tree using data from the CSV file
    InitgPty_element = ET.Element('InitgPty')
    create_xml_element(InitgPty_element, 'Nm', data[0]['initiator_name'])
    GrpHdr_element.append(InitgPty_element)

    for row in data:
        # Create new "PmtInf" element in the XML tree using data from the CSV file
        PmtInf_element = ET.Element('PmtInf')
        cstmr_cdt_trf_initn_element.append(PmtInf_element)

        # Add the PmtInfId and PmtMtd elements to the PmtInf element
        for xml_tag, csv_column in mapping.items():
            if xml_tag in ['PmtInfId', 'PmtMtd']:
                create_xml_element(PmtInf_element, xml_tag, row[csv_column])

        # Create new "BtchBookg" element in the XML tree using data from the CSV file
        create_xml_element(PmtInf_element, 'BtchBookg',
                           row['batch_booking'].lower())

        # Create new "NbOfTxs" element in the XML tree using data from the CSV file
        create_xml_element(PmtInf_element, 'NbOfTxs', row['nb_of_txs'])

        # Create new "CtrlSum" element in the XML tree using data from the CSV file
        create_xml_element(PmtInf_element, 'CtrlSum', row['control_sum'])

        # Create new "PmtTpInf" element in the XML tree using data from the CSV file
        PmtTpInf_element = ET.Element('PmtTpInf')
        child_element = ET.Element('SvcLvl')
        child_element2 = ET.Element('Cd')
        child_element2.text = row['service_level_code']
        child_element.append(child_element2)
        PmtTpInf_element.append(child_element)
        PmtInf_element.append(PmtTpInf_element)

        # Create new "ReqdExctnDt" element in the XML tree using data from the CSV file
        create_xml_element(PmtInf_element, 'ReqdExctnDt',
                           row['requested_execution_date'])

        # Create new "Dbtr" element in the XML tree using data from the CSV file
        Dbtr_element = ET.Element('Dbtr')
        child_element = ET.Element('Nm')
        child_element.text = row['debtor_name']
        Dbtr_element.append(child_element)
        PmtInf_element.append(Dbtr_element)

        # Create new "DbtrAcct" element in the XML tree using data from the CSV file
        DbtrAcct_element = ET.Element('DbtrAcct')
        child_element = ET.Element('Id')
        child_element2 = ET.Element('IBAN')
        # replace with the appropriate value
        child_element2.text = row['debtor_account_IBAN']
        child_element.append(child_element2)
        DbtrAcct_element.append(child_element)
        PmtInf_element.append(DbtrAcct_element)

        # Create new "DbtrAgt" element in the XML tree using data from the CSV file
        DbtrAgt_element = ET.Element('DbtrAgt')
        child_element = ET.Element('FinInstnId')
        child_element2 = ET.Element('BIC')
        # replace with the appropriate value
        child_element2.text = row['debtor_agent_BIC']
        child_element.append(child_element2)
        DbtrAgt_element.append(child_element)
        PmtInf_element.append(DbtrAgt_element)

        # Create new "ChrgBr" element in the XML tree using data from the CSV file
        child_element = ET.Element('ChrgBr')
        # replace with the appropriate value
        child_element.text = row['charge_bearer']
        PmtInf_element.append(child_element)

        # Create new "CdtTrfTxInf" element in the XML tree using data from the CSV file
        CdtTrfTxInf_element = ET.Element('CdtTrfTxInf')

        # Create new "PmtId" element in the XML tree using data from the CSV file
        PmtId_element = ET.Element('PmtId')
        child_element = ET.Element('EndToEndId')
        child_element.text = row['payment_id']
        PmtId_element.append(child_element)
        CdtTrfTxInf_element.append(PmtId_element)

        # Create new "Amt" element in the XML tree using data from the CSV file
        Amt_element = ET.Element('Amt')
        child_element = ET.Element('InstdAmt')
        child_element.text = row['payment_amount']
        child_element.set('Ccy', row['currency'])
        Amt_element.append(child_element)
        CdtTrfTxInf_element.append(Amt_element)

        # Create new "CdtrAgt" element in the XML tree using data from the CSV file
        CdtrAgt_element = ET.Element('CdtrAgt')
        child_element = ET.Element('FinInstnId')
        child_element2 = ET.Element('BIC')
        child_element2.text = row['creditor_agent_BIC']
        child_element.append(child_element2)
        CdtrAgt_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAgt_element)

        # Create new "Cdtr" element in the XML tree using data from the CSV file
        Cdtr_element = ET.Element('Cdtr')
        child_element = ET.Element('Nm')
        child_element.text = row['creditor_name']
        Cdtr_element.append(child_element)
        CdtTrfTxInf_element.append(Cdtr_element)

        # Create new "RmtInf" element in the XML tree using data from the CSV file
        RmtInf_element = ET.Element('RmtInf')
        child_element = ET.Element('Ustrd')
        child_element.text = row['remittance_information']
        RmtInf_element.append(child_element)
        CdtTrfTxInf_element.append(RmtInf_element)

        # Append the new CdtTrfTxInf element to the PmtInf element
        PmtInf_element.append(CdtTrfTxInf_element)

        # Append the new PmtInf element to the CstmrCdtTrfInitn element
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
