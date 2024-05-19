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
This module contains the function `create_xml_v4`, which constructs an XML tree
following the ISO 20022 pain.001.001.04 schema.

The function takes in a root ElementTree element and a list of dictionaries
containing the required data. It then uses Jinja2 templating to dynamically
generate the XML content based on the given data. The function ultimately
returns the root element of the modified XML tree.
"""

# Import the ElementTree package
import xml.etree.ElementTree as et

from jinja2 import Environment, FileSystemLoader


def create_xml_v4(root, data):
    """
    Create an XML tree adhering to the pain.001.001.04 schema.

    Args:
        root (ET.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing data to populate the XML
        document.

    Returns:
        ET.Element: The root element of the modified XML tree.
    """

    # Create CstmrCdtTrfInitn element
    # pylint: disable=E1101
    cstmr_cdt_trf_initn_element = et.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create a Jinja2 environment
    env = Environment(loader=FileSystemLoader("."), autoescape=True)

    # Load the Jinja2 template
    template = env.get_template(
        "pain001/templates/pain.001.001.04/template.xml"
    )

    # Prepare the data for rendering, ensuring all required keys are present
    xml_data_pain001_001_04 = {
        "id": data[0].get("id", ""),
        "date": data[0].get("date", ""),
        "nb_of_txs": data[0].get("nb_of_txs", ""),
        "initiator_name": data[0].get("initiator_name", ""),
        "initiator_street": data[0].get("initiator_street", ""),
        "initiator_building_number": data[0].get(
            "initiator_building_number", ""
        ),
        "initiator_postal_code": data[0].get("initiator_postal_code", ""),
        "initiator_town": data[0].get("initiator_town", ""),
        "initiator_country": data[0].get("initiator_country", ""),
        "payment_information_id": data[0].get("payment_information_id", ""),
        "payment_method": data[0].get("payment_method", ""),
        "batch_booking": data[0].get("batch_booking", ""),
        "requested_execution_date": data[0].get(
            "requested_execution_date", ""
        ),
        "debtor_name": data[0].get("debtor_name", ""),
        "debtor_street": data[0].get("debtor_street", ""),
        "debtor_building_number": data[0].get("debtor_building_number", ""),
        "debtor_postal_code": data[0].get("debtor_postal_code", ""),
        "debtor_town": data[0].get("debtor_town", ""),
        "debtor_country": data[0].get("debtor_country", ""),
        "debtor_account_IBAN": data[0].get("debtor_account_IBAN", ""),
        "debtor_agent_BIC": data[0].get("debtor_agent_BIC", ""),
        "payment_instruction_id": data[0].get("payment_instruction_id", ""),
        "payment_end_to_end_id": data[0].get("payment_end_to_end_id", ""),
        "payment_currency": data[0].get("payment_currency", ""),
        "payment_amount": data[0].get("payment_amount", ""),
        "charge_bearer": data[0].get("charge_bearer", ""),
        "creditor_agent_BIC": data[0].get("creditor_agent_BIC", ""),
        "creditor_name": data[0].get("creditor_name", ""),
        "creditor_street": data[0].get("creditor_street", ""),
        "creditor_building_number": data[0].get(
            "creditor_building_number", ""
        ),
        "creditor_postal_code": data[0].get("creditor_postal_code", ""),
        "creditor_town": data[0].get("creditor_town", ""),
        "creditor_account_IBAN": data[0].get("creditor_account_IBAN", ""),
        "purpose_code": data[0].get("purpose_code", ""),
        "reference_number": data[0].get("reference_number", ""),
        "reference_date": data[0].get("reference_date", ""),
        "transactions": [
            {
                "payment_instruction_id": row.get(
                    "payment_instruction_id", ""
                ),
                "payment_end_to_end_id": row.get("payment_end_to_end_id", ""),
                "payment_currency": row.get("payment_currency", ""),
                "payment_amount": row.get("payment_amount", ""),
                "charge_bearer": row.get("charge_bearer", ""),
                "creditor_agent_BIC": row.get("creditor_agent_BIC", ""),
                "creditor_name": row.get("creditor_name", ""),
                "creditor_street": row.get("creditor_street", ""),
                "creditor_building_number": row.get(
                    "creditor_building_number", ""
                ),
                "creditor_postal_code": row.get("creditor_postal_code", ""),
                "creditor_town": row.get("creditor_town", ""),
                "creditor_account_IBAN": row.get("creditor_account_IBAN", ""),
                "purpose_code": row.get("purpose_code", ""),
                "reference_number": row.get("reference_number", ""),
                "reference_date": row.get("reference_date", ""),
            }
            for row in data[1:]
        ],
    }

    # Render the XML content using the Jinja2 template and the prepared data
    xml_content = template.render(**xml_data_pain001_001_04)

    # Parse the rendered XML content into an ElementTree object
    rendered_xml_tree = et.fromstring(xml_content)

    # Append the rendered XML content as children to the "CstmrCdtTrfInitn" element
    for child in rendered_xml_tree:
        cstmr_cdt_trf_initn_element.append(child)

    return root
