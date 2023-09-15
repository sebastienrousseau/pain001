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

This module contains the create_xml_v9 function which creates the XML tree
for the pain.001.001.09 schema.

"""

# Import the ElementTree package
import xml.etree.ElementTree as ET

from jinja2 import Environment, FileSystemLoader


def create_xml_v9(root, data):
    """Create the XML tree for the pain.001.001.09 schema.

    Args:
        root (ET.Element): The root element of the XML tree.
        data (list): A list of dictionaries containing the data to be added
        to the XML document.

    Returns:
        The root element of the XML tree.
    """

    # Create CstmrCdtTrfInitn element
    # pylint: disable=E1101
    cstmr_cdt_trf_initn_element = ET.Element("CstmrCdtTrfInitn")
    root.append(cstmr_cdt_trf_initn_element)

    # Create a Jinja2 environment
    env = Environment(loader=FileSystemLoader("."), autoescape=True)

    # Load the Jinja2 template
    template = env.get_template(
        "templates/pain.001.001.09/template.xml"
    )

    # Prepare the data
    xml_data_pain001_001_09 = {
        "id": data[0]["id"],
        "date": data[0]["date"],
        "nb_of_txs": data[0]["nb_of_txs"],
        "initiator_name": data[0]["initiator_name"],
        "transactions": [
            {
                "payment_id": row["payment_id"],
                "payment_method": row["payment_method"],
                "payment_nb_of_txs": row["nb_of_txs"],
                "requested_execution_date": row[
                    "requested_execution_date"
                ],
                "debtor_name": row["debtor_name"],
                "debtor_account_IBAN": row["debtor_account_IBAN"],
                "debtor_agent_BICFI": row["debtor_agent_BIC"],
                "charge_bearer": row["charge_bearer"],
                "transactions": [
                    {
                        "payment_id": row["payment_id"],
                        "payment_amount": row["payment_amount"],
                        "payment_currency": row["currency"],
                        "cdtr_agent_BICFI": row["creditor_agent_BIC"],
                        "creditor_name": row["creditor_name"],
                        "cdtr_account_IBAN": row[
                            "creditor_account_IBAN"
                        ],
                        "remittance_information": row[
                            "remittance_information"
                        ],
                    }
                ],
            }
            for row in data[1:]
        ],
    }

    # Render the template
    xml_content = template.render(**xml_data_pain001_001_09)

    # Parse the rendered XML content and append its children to the root
    rendered_xml_tree = ET.fromstring(xml_content)
    for child in rendered_xml_tree:
        cstmr_cdt_trf_initn_element.append(child)

    return root
