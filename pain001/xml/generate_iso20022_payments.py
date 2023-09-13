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

# Import the XML libraries
import xml.etree.ElementTree as ET

# Import the functions from the other modules
from pain001.xml.create_xml_element import create_xml_element

# Import the functions from the other modules
from jinja2 import Environment, FileSystemLoader

def create_common_elements(parent, row, mapping):
    """Create common elements "PmtInfId" and "PmtMtd" in the XML tree using
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




def create_xml_v3(root, data):
    """Create the XML tree for the pain.001.001.03 schema.

    Args:
        root (ElementTree.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing the data to be added
        to the XML document.
        mapping (dict): A dictionary mapping the Data column names to the XML
        element names.

    Returns:
        The root element of the XML tree.
    """

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create a Jinja2 environment
    env = Environment(loader=FileSystemLoader('.'))

    # Load the Jinja2 template
    template = env.get_template('templates/pain.001.001.03/template.xml')

    # Prepare the data for rendering
    xml_data_pain001_001_03 = {
        'id': data[0]['id'],
        'date': data[0]['date'],
        'nb_of_txs': data[0]['nb_of_txs'],
        'initiator_name': data[0]['initiator_name'],
        'initiator_street_name': data[0]['initiator_street_name'],
        'initiator_building_number': data[0]['initiator_building_number'],
        'initiator_postal_code': data[0]['initiator_postal_code'],
        'initiator_town_name': data[0]['initiator_town_name'],
        'initiator_country_code': data[0]['initiator_country_code'],
        'payment_id': data[0]['payment_id'],
        'payment_method': data[0]['payment_method'],
        'batch_booking': data[0]['batch_booking'],
        'requested_execution_date': data[0]['requested_execution_date'],
        'debtor_name': data[0]['debtor_name'],
        'debtor_street_name': data[0]['debtor_street_name'],
        'debtor_building_number': data[0]['debtor_building_number'],
        'debtor_postal_code': data[0]['debtor_postal_code'],
        'debtor_town_name': data[0]['debtor_town_name'],
        'debtor_country_code': data[0]['debtor_country_code'],
        'debtor_account_IBAN': data[0]['debtor_account_IBAN'],
        'debtor_agent_BIC': data[0]['debtor_agent_BIC'],
        'charge_bearer': data[0]['charge_bearer'],
        'transactions': [
            {
                'payment_id': row['payment_id'],
                'payment_amount': row.get('payment_amount', ''),
                'payment_currency': row.get('payment_currency', ''),
                'charge_bearer': row['charge_bearer'],
                'creditor_agent_BIC': row['creditor_agent_BIC'],
                'creditor_name': row['creditor_name'],
                'creditor_street_name': row['creditor_street_name'],
                'creditor_building_number': row['creditor_building_number'],
                'creditor_postal_code': row['creditor_postal_code'],
                'creditor_town_name': row['creditor_town_name'],
                'creditor_country_code': row['creditor_country_code'],
                'creditor_account_IBAN': row['creditor_account_IBAN'],
                'purpose_code': row['purpose_code'],
                'reference_number': row['reference_number'],
                'reference_date': row['reference_date'],
            }
            for row in data[1:]
        ],
    }

    # Render the template
    xml_content = template.render(**xml_data_pain001_001_03)

    # Parse the rendered XML content and append its children to the root
    rendered_xml_tree = ET.fromstring(xml_content)
    for child in rendered_xml_tree:
        cstmr_cdt_trf_initn_element.append(child)

    return root

def create_xml_v4(root, data):
    """Create the XML tree for the pain.001.001.04 schema.

    Args:
        root (ElementTree.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing the data to be added
        to the XML document.
        mapping (dict): A dictionary mapping the Data column names to the XML
        element names.

    Returns:
        The root element of the XML tree.
    """

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create a Jinja2 environment
    env = Environment(loader=FileSystemLoader('.'))

    # Load the Jinja2 template
    template = env.get_template('templates/pain.001.001.04/template.xml')

    # Prepare the data for rendering
    xml_data_pain001_001_04 = {
    'id': '{{id}}',
    'date': '{{date}}',
    'nb_of_txs': '{{nb_of_txs}}',

    'initiator_name': '{{initiator_name}}',
    'initiator_street': '{{initiator_street}}', 
    'initiator_building_number': '{{initiator_building_number}}',
    'initiator_postal_code': '{{initiator_postal_code}}',
    'initiator_town': '{{initiator_town}}',
    'initiator_country': '{{initiator_country}}',

    'payment_information_id': '{{payment_information_id}}',
    'payment_method': '{{payment_method}}',
    'batch_booking': '{{batch_booking}}', 
    'requested_execution_date': '{{requested_execution_date}}',

    'debtor_name': '{{debtor_name}}',
    'debtor_street': '{{debtor_street}}',
    'debtor_building_number': '{{debtor_building_number}}',
    'debtor_postal_code': '{{debtor_postal_code}}',
    'debtor_town': '{{debtor_town}}',
    'debtor_country': '{{debtor_country}}',
    'debtor_account_IBAN': '{{debtor_account_IBAN}}',
    'debtor_agent_BICFI': '{{debtor_agent_BICFI}}',

    'payment_instruction_id': '{{payment_instruction_id}}',
    'payment_end_to_end_id': '{{payment_end_to_end_id}}',
    'payment_currency': '{{payment_currency}}',
    'payment_amount': '{{payment_amount}}',
    'charge_bearer': '{{charge_bearer}}',
    'creditor_agent_BIC': '{{creditor_agent_BIC}}',
    'creditor_name': '{{creditor_name}}',
    'creditor_street': '{{creditor_street}}',
    'creditor_building_number': '{{creditor_building_number}}',
    'creditor_postal_code': '{{creditor_postal_code}}',
    'creditor_town': '{{creditor_town}}',
    'creditor_account_IBAN': '{{creditor_account_IBAN}}',
    'purpose_code': '{{purpose_code}}',
    'reference_number': '{{reference_number}}',
    'reference_date': '{{reference_date}}',
    'transactions': [
        {
        'payment_instruction_id': '{{payment_instruction_id}}',
        'payment_end_to_end_id': '{{payment_end_to_end_id}}',
        'payment_currency': '{{payment_currency}}',
        'payment_amount': '{{payment_amount}}',
        'charge_bearer': '{{charge_bearer}}',
        'creditor_agent_BIC': '{{creditor_agent_BIC}}',
        'creditor_name': '{{creditor_name}}',
        'creditor_street': '{{creditor_street}}',
        'creditor_building_number': '{{creditor_building_number}}',
        'creditor_postal_code': '{{creditor_postal_code}}',
        'creditor_town': '{{creditor_town}}',
        'creditor_account_IBAN': '{{creditor_account_IBAN}}',
        'purpose_code': '{{purpose_code}}',
        'reference_number': '{{reference_number}}',
        'reference_date': '{{reference_date}}'
        }
    ]
    }

    # Render the template
    xml_content = template.render(**xml_data_pain001_001_04)

    # Parse the rendered XML content and append its children to the root
    rendered_xml_tree = ET.fromstring(xml_content)
    for child in rendered_xml_tree:
        cstmr_cdt_trf_initn_element.append(child)

    return root


def create_xml_v9(root, data, mapping):
    """Creates an XML document for the pain.001.001.09 schema.

    Args:
        root (ElementTree.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing the data to be added
        to the XML document.
        mapping (dict): A dictionary mapping the Data column names to the XML
        element names.

    Returns:
        The root element of the XML tree.
    """

    # Create CstmrCdtTrfInitn element
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create GrpHdr element and append it to CstmrCdtTrfInitn
    GrpHdr_element = ET.Element("GrpHdr")
    cstmr_cdt_trf_initn_element.append(GrpHdr_element)

    # Add the MsgId, CreDtTm, and NbOfTxs elements to the GrpHdr element
    for xml_tag, csv_column in mapping.items():
        if xml_tag in ["MsgId", "CreDtTm", "NbOfTxs"]:
            create_xml_element(
                GrpHdr_element, xml_tag, data[0][csv_column]
            )

    # Create new "InitgPty" element in the XML tree using data from the
    # Data file
    InitgPty_element = ET.Element("InitgPty")
    create_xml_element(
        InitgPty_element, "Nm", data[0]["initiator_name"]
    )
    GrpHdr_element.append(InitgPty_element)

    for row in data:
        # Create new "PmtInf" element in the XML tree using data from
        # the Data file
        PmtInf_element = ET.Element("PmtInf")
        cstmr_cdt_trf_initn_element.append(PmtInf_element)

        create_common_elements(PmtInf_element, row, mapping)

        Dbtr_element = ET.Element("ReqdExctnDt")
        child_element = ET.Element("Dt")
        child_element.text = row["requested_execution_date"]
        Dbtr_element.append(child_element)
        PmtInf_element.append(Dbtr_element)

        # Create new "Dbtr" element in the XML tree using data from
        # the Data file
        Dbtr_element = ET.Element("Dbtr")
        child_element = ET.Element("Nm")
        child_element.text = row["debtor_name"]
        Dbtr_element.append(child_element)
        PmtInf_element.append(Dbtr_element)

        # Create new "DbtrAcct" element in the XML tree using data
        # from the Data file
        DbtrAcct_element = ET.Element("DbtrAcct")
        child_element = ET.Element("Id")
        child_element2 = ET.Element("IBAN")
        # replace with the appropriate value
        child_element2.text = row["debtor_account_IBAN"]
        child_element.append(child_element2)
        DbtrAcct_element.append(child_element)
        PmtInf_element.append(DbtrAcct_element)

        # Create new "DbtrAgt" element in the XML tree using data
        # from the Data file
        DbtrAgt_element = ET.Element("DbtrAgt")
        child_element = ET.Element("FinInstnId")
        child_element2 = ET.Element("BICFI")
        # replace with the appropriate value
        child_element2.text = row["debtor_agent_BIC"]
        child_element2.set(
            "xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
        )
        child_element.append(child_element2)
        DbtrAgt_element.append(child_element)
        PmtInf_element.append(DbtrAgt_element)

        # Create new "ChrgBr" element in the XML tree using data
        # from the Data file
        child_element = ET.Element("ChrgBr")
        # replace with the appropriate value
        child_element.text = row["charge_bearer"]
        PmtInf_element.append(child_element)

        # Create new "CdtTrfTxInf" element in the XML tree using data
        # from the Data file
        CdtTrfTxInf_element = ET.Element("CdtTrfTxInf")

        # Create new "PmtId" element in the XML tree using data
        # from the Data file
        PmtId_element = ET.Element("PmtId")
        child_element = ET.Element("EndToEndId")
        child_element.text = row["payment_id"]
        PmtId_element.append(child_element)
        CdtTrfTxInf_element.append(PmtId_element)

        # Create new "Amt" element in the XML tree using data
        # from the Data file
        Amt_element = ET.Element("Amt")
        child_element = ET.Element("InstdAmt")
        child_element.text = row["payment_amount"]
        child_element.set("Ccy", row["currency"])
        Amt_element.append(child_element)
        CdtTrfTxInf_element.append(Amt_element)

        # Create new "CdtrAgt" element in the XML tree using data
        # from the Data file
        CdtrAgt_element = ET.Element("CdtrAgt")
        child_element = ET.Element("FinInstnId")
        child_element2 = ET.Element("BICFI")
        # replace with the appropriate value
        child_element2.text = row["creditor_agent_BIC"]
        child_element2.set(
            "xmlns", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
        )
        child_element.append(child_element2)
        CdtrAgt_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAgt_element)

        # Create new "Cdtr" element in the XML tree using data
        # from the Data file
        Cdtr_element = ET.Element("Cdtr")
        child_element = ET.Element("Nm")
        child_element.text = row["creditor_name"]
        Cdtr_element.append(child_element)
        CdtTrfTxInf_element.append(Cdtr_element)

        # Create new "CdtrAcct" element in the XML tree using data
        # from the CSV file
        CdtrAcct_element = ET.Element("CdtrAcct")
        child_element = ET.Element("Id")
        child_element2 = ET.Element("IBAN")
        child_element2.text = row["creditor_agent_BIC"]
        child_element.append(child_element2)
        CdtrAcct_element.append(child_element)
        CdtTrfTxInf_element.append(CdtrAcct_element)

        # Create new "RmtInf" element in the XML tree using data
        # from the Data file
        RmtInf_element = ET.Element("RmtInf")
        child_element = ET.Element("Ustrd")
        child_element.text = row["remittance_information"]
        RmtInf_element.append(child_element)
        CdtTrfTxInf_element.append(RmtInf_element)

        # Append the new CdtTrfTxInf element to the PmtInf element
        PmtInf_element.append(CdtTrfTxInf_element)

        # Append the new PmtInf element to the CstmrCdtTrfInitn element
        cstmr_cdt_trf_initn_element.append(PmtInf_element)

        # Create new "SplmtryData" elements in the XML tree using data
        # from the Data file"
        # Create the main elements
        SplmtryData_element = ET.Element("SplmtryData")
        Envlp_element = ET.SubElement(SplmtryData_element, "Envlp")
        child_element = ET.SubElement(Envlp_element, "WC")
        CdtTrfTxInf_element.append(SplmtryData_element)
