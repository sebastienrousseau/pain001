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
This module contains the function `create_xml_v3`, which constructs an XML tree
for the ISO 20022 pain.001.001.03 schema.

The function takes in a root ElementTree element and a list of dictionaries
containing the required data. It then uses Jinja2 templating to dynamically
generate the XML content based on the given data. The function ultimately
returns the root element of the modified XML tree.
"""

import xml.etree.ElementTree as et
from jinja2 import Environment, FileSystemLoader


def create_xml_v3(root, data):
    """
    Constructs an XML tree based on the pain.001.001.03 schema and appends it
    to the provided root element. This function uses the Jinja2 templating
    engine to generate the XML content.

    Parameters
    ----------
    root : xml.etree.ElementTree.Element
        The root element of the XML tree to which the new elements will be
        appended.
    data : list of dict
        A list of dictionaries, where each dictionary contains the data to be
        added to the XML document. The first dictionary usually contains common
        attributes that are used throughout the XML, while the subsequent
        dictionaries contain transaction-specific attributes.

    Returns
    -------
    xml.etree.ElementTree.Element
        The updated root element of the XML tree.
    """

    # Create the "CstmrCdtTrfInitn" element and append it to the root
    cstmr_cdt_trf_initn_element = et.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Initialize the Jinja2 environment
    env = Environment(loader=FileSystemLoader("."), autoescape=True)

    # Load the Jinja2 template for the pain.001.001.03 schema
    template = env.get_template(
        "pain001/templates/pain.001.001.03/template.xml"
    )

    # Prepare the data dictionary for rendering through the Jinja2 template
    # This dictionary is a reformatted version of the `data` parameter, made to
    # fit the template's requirements.
    xml_data_pain001_001_03 = {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0]["nb_of_txs"],
        "initiator_name": data[0]["initiator_name"],
        "initiator_street_name": data[0]["initiator_street_name"],
        "initiator_building_number": data[0]["initiator_building_number"],
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
                "creditor_building_number": row["creditor_building_number"],
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

    # Render the XML content using the Jinja2 template and the prepared data
    xml_content = template.render(**xml_data_pain001_001_03)

    # Parse the rendered XML content into an ElementTree object
    rendered_xml_tree = et.fromstring(xml_content)

    # Append the rendered XML content as children to the "CstmrCdtTrfInitn"
    # element
    for child in rendered_xml_tree:
        cstmr_cdt_trf_initn_element.append(child)

    return root
