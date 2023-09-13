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

This module contains the create_xml_v3 function which creates the XML tree
for the pain.001.001.03 schema.

"""

import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader


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
    # pylint: disable=E1101
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create a Jinja2 environment
    env = Environment(loader=FileSystemLoader("."))

    # Load the Jinja2 template
    template = env.get_template(
        "templates/pain.001.001.03/template.xml"
    )

    # Prepare the data for rendering
    xml_data_pain001_001_03 = {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0]["nb_of_txs"],
        "initiator_name": data[0]["initiator_name"],
        "initiator_street_name": data[0]["initiator_street_name"],
        "initiator_building_number": data[0][
            "initiator_building_number"
        ],
        "initiator_postal_code": data[0]["initiator_postal_code"],
        "initiator_town_name": data[0]["initiator_town_name"],
        "initiator_country_code": data[0]["initiator_country_code"],
        "payment_id": data[0]["payment_id"],
        "payment_method": data[0]["payment_method"],
        "batch_booking": data[0]["batch_booking"],
        "requested_execution_date": data[0]["requested_execution_date"],
        "debtor_name": data[0]["debtor_name"],
        "debtor_street_name": data[0]["debtor_street_name"],
        "debtor_building_number": data[0]["debtor_building_number"],
        "debtor_postal_code": data[0]["debtor_postal_code"],
        "debtor_town_name": data[0]["debtor_town_name"],
        "debtor_country_code": data[0]["debtor_country_code"],
        "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
        "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
        "charge_bearer": data[0]["charge_bearer"],
        "transactions": [
            {
                "payment_id": row["payment_id"],
                "payment_amount": row.get("payment_amount", ""),
                "payment_currency": row.get("payment_currency", ""),
                "charge_bearer": row["charge_bearer"],
                "creditor_agent_BIC": row["creditor_agent_BIC"],
                "creditor_name": row["creditor_name"],
                "creditor_street_name": row["creditor_street_name"],
                "creditor_building_number": row[
                    "creditor_building_number"
                ],
                "creditor_postal_code": row["creditor_postal_code"],
                "creditor_town_name": row["creditor_town_name"],
                "creditor_country_code": row["creditor_country_code"],
                "creditor_account_IBAN": row["creditor_account_IBAN"],
                "purpose_code": row["purpose_code"],
                "reference_number": row["reference_number"],
                "reference_date": row["reference_date"],
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
