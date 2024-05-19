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

# XML generator function that creates the XML file from the CSV data
# and the mapping dictionary between XML tags and CSV columns names and
# writes it to a file in the same directory as the CSV file

# Import the CSV library
import sys

from jinja2 import Environment, FileSystemLoader
from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)
from pain001.xml.create_xml_v3 import create_xml_v3
from pain001.xml.create_xml_v4 import create_xml_v4
from pain001.xml.create_xml_v5 import create_xml_v5
from pain001.xml.create_xml_v6 import create_xml_v6
from pain001.xml.create_xml_v7 import create_xml_v7
from pain001.xml.create_xml_v8 import create_xml_v8
from pain001.xml.create_xml_v9 import create_xml_v9
from pain001.xml.validate_via_xsd import validate_via_xsd


def generate_xml(
    data, payment_initiation_message_type, xml_file_path, xsd_file_path
):
    """Generates an ISO 20022 pain.001 XML file from input data.

    Args:
        data: List of dictionaries containing payment data
        payment_initiation_message_type: String indicating message type
        such as "pain.001.001.03, pain.001.001.04, pain.001.001.05,
        pain.001.001.06, pain.001.001.07, pain.001.001.08, etc."
        xml_file_path: Path to write generated XML file to
        xsd_file_path: Path to XML schema file for validation

    Returns:
        None
    """

    # Define a mapping between the XML types and the XML generators
    xml_generators = {
        "pain.001.001.03": create_xml_v3,
        "pain.001.001.04": create_xml_v4,
        "pain.001.001.05": create_xml_v5,
        "pain.001.001.06": create_xml_v6,
        "pain.001.001.07": create_xml_v7,
        "pain.001.001.08": create_xml_v8,
        "pain.001.001.09": create_xml_v9,
    }

    # Check if the provided payment_initiation_message_type exists in
    # the mapping
    if payment_initiation_message_type in xml_generators:
        # Get the corresponding XML generation function for the XML type
        # xml_generator = xml_generators[payment_initiation_message_type]

        # Check if data is not empty
        if not data:
            print("Error: No data to process.")
            sys.exit(1)

        # Create a Jinja2 environment
        env = Environment(loader=FileSystemLoader("."), autoescape=True)

        # Load the Jinja2 template
        template = env.get_template(xml_file_path)

        # Prepare the data for rendering
        if payment_initiation_message_type == "pain.001.001.03":
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
                "requested_execution_date": data[0][
                    "requested_execution_date"
                ],
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
                    for row in data[0:]
                ],
            }
        elif payment_initiation_message_type == "pain.001.001.04":
            xml_data_pain001_001_04 = {
                "id": data[0].get("id", ""),
                "date": data[0].get("date", ""),
                "nb_of_txs": data[0].get("nb_of_txs", ""),
                "initiator_name": data[0].get("initiator_name", ""),
                "initiator_street": data[0].get("initiator_street_name", ""),
                "initiator_building_number": data[0].get(
                    "initiator_building_number", ""
                ),
                "initiator_postal_code": data[0].get(
                    "initiator_postal_code", ""
                ),
                "initiator_town": data[0].get("initiator_town_name", ""),
                "initiator_country": data[0].get("initiator_country_code", ""),
                "payment_information_id": data[0].get("payment_id", ""),
                "payment_method": data[0].get("payment_method", ""),
                "batch_booking": data[0].get("batch_booking", ""),
                "requested_execution_date": data[0].get(
                    "requested_execution_date", ""
                ),
                "debtor_name": data[0].get("debtor_name", ""),
                "debtor_street": data[0].get("debtor_street_name", ""),
                "debtor_building_number": data[0].get(
                    "debtor_building_number", ""
                ),
                "debtor_postal_code": data[0].get("debtor_postal_code", ""),
                "debtor_town": data[0].get("debtor_town_name", ""),
                "debtor_country": data[0].get("debtor_country_code", ""),
                "debtor_account_IBAN": data[0].get("debtor_account_IBAN", ""),
                "debtor_agent_BIC": data[0].get("debtor_agent_BIC", ""),
                "debtor_agent_account_IBAN": data[0].get(
                    "debtor_agent_account_IBAN", ""
                ),
                "instruction_for_debtor_agent": data[0].get(
                    "instruction_for_debtor_agent", ""
                ),
                "charge_bearer": data[0].get("charge_bearer", ""),
                "charge_account_IBAN": data[0].get("charge_account_IBAN", ""),
                "charge_agent_BICFI": data[0].get("charge_agent_BICFI", ""),
                "payment_instruction_id": data[0].get(
                    "payment_instruction_id", ""
                ),
                "payment_end_to_end_id": data[0].get(
                    "payment_end_to_end_id", ""
                ),
                "payment_currency": data[0].get("payment_currency", ""),
                "payment_amount": data[0].get("payment_amount", ""),
                "creditor_agent_BIC": data[0].get("creditor_agent_BIC", ""),
                "creditor_name": data[0].get("creditor_name", ""),
                "creditor_street": data[0].get("creditor_street", ""),
                "creditor_building_number": data[0].get(
                    "creditor_building_number", ""
                ),
                "creditor_postal_code": data[0].get(
                    "creditor_postal_code", ""
                ),
                "creditor_town": data[0].get("creditor_town", ""),
                "creditor_account_IBAN": data[0].get(
                    "creditor_account_IBAN", ""
                ),
                "purpose_code": data[0].get("purpose_code", ""),
                "reference_number": data[0].get("reference_number", ""),
                "reference_date": data[0].get("reference_date", ""),
                "transactions": [
                    {
                        "payment_instruction_id": row.get("payment_id", ""),
                        "payment_end_to_end_id": row.get(
                            "reference_number", ""
                        ),
                        "payment_currency": row.get("payment_currency", "EUR"),
                        "payment_amount": row.get("payment_amount", ""),
                        "charge_bearer": row.get("charge_bearer", ""),
                        "creditor_agent_BIC": row.get(
                            "creditor_agent_BIC", ""
                        ),
                        "creditor_name": row.get("creditor_name", ""),
                        "creditor_street": row.get("creditor_street_name", ""),
                        "creditor_building_number": row.get(
                            "creditor_building_number", ""
                        ),
                        "creditor_postal_code": row.get(
                            "creditor_postal_code", ""
                        ),
                        "creditor_town": row.get("creditor_town_name", ""),
                        "creditor_account_IBAN": row.get(
                            "creditor_account_IBAN", ""
                        ),
                        "purpose_code": row.get("purpose_code", ""),
                        "reference_number": row.get("reference_number", ""),
                        "reference_date": row.get("reference_date", ""),
                    }
                    for row in data[0:]
                ],
            }
        elif payment_initiation_message_type == "pain.001.001.05":
            xml_data_pain001_001_05 = {
                "id": data[0]["id"],
                "date": data[0]["date"],
                "nb_of_txs": data[0]["nb_of_txs"],
                "ctrl_sum": data[0]["ctrl_sum"],
                "initiator_name": data[0]["initiator_name"],
                "initiator_street_name": data[0]["initiator_street_name"],
                "initiator_building_number": data[0][
                    "initiator_building_number"
                ],
                "initiator_postal_code": data[0]["initiator_postal_code"],
                "initiator_town": data[0]["initiator_town_name"],
                "initiator_country": data[0]["initiator_country"],
                "ultimate_debtor_name": data[0]["ultimate_debtor_name"],
                "service_level_code": data[0]["service_level_code"],
                "requested_execution_date": data[0][
                    "requested_execution_date"
                ],
                "payment_information_id": data[0]["payment_information_id"],
                "payment_method": data[0]["payment_method"],
                "batch_booking": data[0]["batch_booking"],
                "debtor_name": data[0]["debtor_name"],
                "debtor_street": data[0]["debtor_street"],
                "debtor_building_number": data[0]["debtor_building_number"],
                "debtor_postal_code": data[0]["debtor_postal_code"],
                "debtor_town": data[0]["debtor_town"],
                "debtor_country": data[0]["debtor_country"],
                "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
                "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
                "payment_instruction_id": data[0]["payment_instruction_id"],
                "payment_end_to_end_id": data[0]["payment_end_to_end_id"],
                "payment_currency": data[0]["payment_currency"],
                "payment_amount": data[0]["payment_amount"],
                "charge_bearer": data[0]["charge_bearer"],
                "creditor_name": data[0]["creditor_name"],
                "creditor_street": data[0]["creditor_street"],
                "creditor_building_number": data[0][
                    "creditor_building_number"
                ],
                "creditor_postal_code": data[0]["creditor_postal_code"],
                "creditor_town": data[0]["creditor_town"],
                "creditor_country": data[0]["creditor_country"],
                "creditor_account_IBAN": data[0]["creditor_account_IBAN"],
                "creditor_agent_BICFI": data[0]["creditor_agent_BICFI"],
                "purpose_code": data[0]["purpose_code"],
                "reference_number": data[0]["reference_number"],
                "reference_date": data[0]["reference_date"],
            }

        elif payment_initiation_message_type == "pain.001.001.06":
            xml_data_pain001_001_06 = {
                "id": data[0]["id"],
                "date": data[0]["date"],
                "nb_of_txs": data[0]["nb_of_txs"],
                "ctrl_sum": data[0]["ctrl_sum"],
                "initiator_name": data[0]["initiator_name"],
                "initiator_street_name": data[0]["initiator_street_name"],
                "initiator_building_number": data[0][
                    "initiator_building_number"
                ],
                "initiator_postal_code": data[0]["initiator_postal_code"],
                "initiator_town": data[0]["initiator_town"],
                "initiator_country": data[0]["initiator_country"],
                "payment_information_id": data[0]["payment_information_id"],
                "payment_method": data[0]["payment_method"],
                "batch_booking": data[0]["batch_booking"],
                "requested_execution_date": data[0][
                    "requested_execution_date"
                ],
                "debtor_name": data[0]["debtor_name"],
                "debtor_street": data[0]["debtor_street"],
                "debtor_building_number": data[0]["debtor_building_number"],
                "debtor_postal_code": data[0]["debtor_postal_code"],
                "debtor_town": data[0]["debtor_town"],
                "debtor_country": data[0]["debtor_country"],
                "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
                "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
                "payment_instruction_id": data[0]["payment_instruction_id"],
                "payment_end_to_end_id": data[0]["payment_end_to_end_id"],
                "payment_currency": data[0]["payment_currency"],
                "payment_amount": data[0]["payment_amount"],
                "charge_bearer": data[0]["charge_bearer"],
                "creditor_name": data[0]["creditor_name"],
                "creditor_street": data[0]["creditor_street"],
                "creditor_building_number": data[0][
                    "creditor_building_number"
                ],
                "creditor_postal_code": data[0]["creditor_postal_code"],
                "creditor_town": data[0]["creditor_town"],
                "creditor_country": data[0]["creditor_country"],
                "creditor_account_IBAN": data[0]["creditor_account_IBAN"],
                "creditor_agent_BICFI": data[0]["creditor_agent_BICFI"],
                "purpose_code": data[0]["purpose_code"],
                "reference_number": data[0]["reference_number"],
                "reference_date": data[0]["reference_date"],
                "transactions": [
                    {
                        "payment_id": row["payment_id"],
                        "payment_amount": row["payment_amount"],
                        "payment_currency": row.get("payment_currency", ""),
                        "charge_bearer": row["charge_bearer"],
                        "creditor_agent_BIC": row["creditor_agent_BIC"],
                        "creditor_name": row["creditor_name"],
                        "creditor_account_IBAN": row["creditor_account_IBAN"],
                        "creditor_remittance_information": row[
                            "remittance_information"
                        ],
                    }
                    for row in data[0:]
                ],
            }

        elif payment_initiation_message_type == "pain.001.001.07":
            xml_data_pain001_001_07 = {
                "id": data[0]["id"],
                "date": data[0]["date"],
                "nb_of_txs": data[0]["nb_of_txs"],
                "ctrl_sum": data[0]["ctrl_sum"],
                "initiator_name": data[0]["initiator_name"],
                "initiator_street_name": data[0]["initiator_street_name"],
                "initiator_building_number": data[0][
                    "initiator_building_number"
                ],
                "initiator_postal_code": data[0]["initiator_postal_code"],
                "initiator_town": data[0]["initiator_town"],
                "initiator_country": data[0]["initiator_country"],
                "payment_information_id": data[0]["payment_information_id"],
                "payment_method": data[0]["payment_method"],
                "batch_booking": data[0]["batch_booking"],
                "requested_execution_date": data[0][
                    "requested_execution_date"
                ],
                "debtor_name": data[0]["debtor_name"],
                "debtor_street": data[0]["debtor_street"],
                "debtor_building_number": data[0]["debtor_building_number"],
                "debtor_postal_code": data[0]["debtor_postal_code"],
                "debtor_town": data[0]["debtor_town"],
                "debtor_country": data[0]["debtor_country"],
                "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
                "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
                "payment_instruction_id": data[0]["payment_instruction_id"],
                "payment_end_to_end_id": data[0]["payment_end_to_end_id"],
                "payment_currency": data[0]["payment_currency"],
                "payment_amount": data[0]["payment_amount"],
                "charge_bearer": data[0]["charge_bearer"],
                "creditor_name": data[0]["creditor_name"],
                "creditor_street": data[0]["creditor_street"],
                "creditor_building_number": data[0][
                    "creditor_building_number"
                ],
                "creditor_postal_code": data[0]["creditor_postal_code"],
                "creditor_town": data[0]["creditor_town"],
                "creditor_country": data[0]["creditor_country"],
                "creditor_account_IBAN": data[0]["creditor_account_IBAN"],
                "creditor_agent_BICFI": data[0]["creditor_agent_BICFI"],
                "purpose_code": data[0]["purpose_code"],
                "reference_number": data[0]["reference_number"],
                "reference_date": data[0]["reference_date"],
                "transactions": [
                    {
                        "payment_id": row["payment_id"],
                        "payment_amount": row["payment_amount"],
                        "payment_currency": row.get("payment_currency", ""),
                        "charge_bearer": row["charge_bearer"],
                        "creditor_agent_BIC": row["creditor_agent_BIC"],
                        "creditor_name": row["creditor_name"],
                        "creditor_account_IBAN": row["creditor_account_IBAN"],
                        "creditor_remittance_information": row[
                            "remittance_information"
                        ],
                    }
                    for row in data[0:]
                ],
            }

        elif payment_initiation_message_type == "pain.001.001.08":
            xml_data_pain001_001_08 = {
                "id": data[0]["id"],
                "date": data[0]["date"],
                "nb_of_txs": data[0]["nb_of_txs"],
                "ctrl_sum": data[0]["ctrl_sum"],
                "initiator_name": data[0]["initiator_name"],
                "initiator_street_name": data[0]["initiator_street_name"],
                "initiator_building_number": data[0][
                    "initiator_building_number"
                ],
                "initiator_postal_code": data[0]["initiator_postal_code"],
                "initiator_town": data[0]["initiator_town"],
                "initiator_country": data[0]["initiator_country"],
                "payment_information_id": data[0]["payment_information_id"],
                "payment_method": data[0]["payment_method"],
                "batch_booking": data[0]["batch_booking"],
                "requested_execution_date": data[0][
                    "requested_execution_date"
                ],
                "debtor_name": data[0]["debtor_name"],
                "debtor_street": data[0]["debtor_street"],
                "debtor_building_number": data[0]["debtor_building_number"],
                "debtor_postal_code": data[0]["debtor_postal_code"],
                "debtor_town": data[0]["debtor_town"],
                "debtor_country": data[0]["debtor_country"],
                "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
                "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
                "payment_instruction_id": data[0]["payment_instruction_id"],
                "payment_end_to_end_id": data[0]["payment_end_to_end_id"],
                "payment_currency": data[0]["payment_currency"],
                "payment_amount": data[0]["payment_amount"],
                "charge_bearer": data[0]["charge_bearer"],
                "creditor_name": data[0]["creditor_name"],
                "creditor_street": data[0]["creditor_street"],
                "creditor_building_number": data[0][
                    "creditor_building_number"
                ],
                "creditor_postal_code": data[0]["creditor_postal_code"],
                "creditor_town": data[0]["creditor_town"],
                "creditor_country": data[0]["creditor_country"],
                "creditor_account_IBAN": data[0]["creditor_account_IBAN"],
                "creditor_agent_BICFI": data[0]["creditor_agent_BICFI"],
                "purpose_code": data[0]["purpose_code"],
                "reference_number": data[0]["reference_number"],
                "reference_date": data[0]["reference_date"],
                "transactions": [
                    {
                        "payment_id": row["payment_id"],
                        "payment_amount": row["payment_amount"],
                        "payment_currency": row.get("payment_currency", ""),
                        "charge_bearer": row["charge_bearer"],
                        "creditor_agent_BIC": row["creditor_agent_BIC"],
                        "creditor_name": row["creditor_name"],
                        "creditor_account_IBAN": row["creditor_account_IBAN"],
                        "creditor_remittance_information": row[
                            "remittance_information"
                        ],
                    }
                    for row in data[0:]
                ],
            }

        elif payment_initiation_message_type == "pain.001.001.09":
            xml_data_pain001_001_09 = {
                "id": data[0]["id"],
                "date": data[0]["date"],
                "nb_of_txs": data[0]["nb_of_txs"],
                "initiator_name": data[0]["initiator_name"],
                "payment_id": data[0]["payment_id"],
                "payment_method": data[0]["payment_method"],
                "payment_nb_of_txs": data[0]["nb_of_txs"],
                "requested_execution_date": data[0][
                    "requested_execution_date"
                ],
                "debtor_name": data[0]["debtor_name"],
                "debtor_account_IBAN": data[0]["debtor_account_IBAN"],
                "debtor_agent_BIC": data[0]["debtor_agent_BIC"],
                "charge_bearer": data[0]["charge_bearer"],
                "transactions": [
                    {
                        "payment_id": row["payment_id"],
                        "payment_amount": row["payment_amount"],
                        "payment_currency": row.get("payment_currency", ""),
                        "charge_bearer": row["charge_bearer"],
                        "creditor_agent_BIC": row["creditor_agent_BIC"],
                        "creditor_name": row["creditor_name"],
                        "creditor_account_IBAN": row["creditor_account_IBAN"],
                        "creditor_remittance_information": row[
                            "remittance_information"
                        ],
                    }
                    for row in data[0:]
                ],
            }

        # Check if the payment initiation message type is "pain.001.001.03"
        if payment_initiation_message_type == "pain.001.001.03":
            # xml_data_pain001_001_03 = {}
            xml_data = xml_data_pain001_001_03
        # Check if the payment initiation message type is "pain.001.001.04"
        elif payment_initiation_message_type == "pain.001.001.04":
            # xml_data_pain001_001_04 = {}
            xml_data = xml_data_pain001_001_04
        # Check if the payment initiation message type is "pain.001.001.05"
        elif payment_initiation_message_type == "pain.001.001.05":
            # xml_data_pain001_001_05 = {}
            xml_data = xml_data_pain001_001_05
        # Check if the payment initiation message type is "pain.001.001.06"
        elif payment_initiation_message_type == "pain.001.001.06":
            # xml_data_pain001_001_06 = {}
            xml_data = xml_data_pain001_001_06
        # Check if the payment initiation message type is "pain.001.001.07"
        elif payment_initiation_message_type == "pain.001.001.07":
            # xml_data_pain001_001_07 = {}
            xml_data = xml_data_pain001_001_07
        # Check if the payment initiation message type is "pain.001.001.08"
        elif payment_initiation_message_type == "pain.001.001.08":
            # xml_data_pain001_001_08 = {}
            xml_data = xml_data_pain001_001_08
        # Check if the payment initiation message type is "pain.001.001.09"
        elif payment_initiation_message_type == "pain.001.001.09":
            # xml_data_pain001_001_09 = {}
            xml_data = xml_data_pain001_001_09
        else:
            # If it's not supported, print an error message and exit
            print(
                f"""
The payment initiation message type {payment_initiation_message_type} is not
supported at this time.
"""
            )
            sys.exit(1)

        # Render the template
        xml_content = template.render(**xml_data)

        # Generate updated XML file path
        updated_xml_file_path = generate_updated_xml_file_path(
            xml_file_path, payment_initiation_message_type
        )

        # Write the XML content to the file without extra spacing
        with open(updated_xml_file_path, "w") as xml_file:
            xml_file.write(xml_content)

        print(f"A new XML file has been created at `{updated_xml_file_path}`")

        # Validate the updated XML file against the XSD schema
        is_valid = validate_via_xsd(updated_xml_file_path, xsd_file_path)

        if not is_valid:
            print("Error: Invalid XML data.")
            sys.exit(1)
        else:
            print(f"The XML has been validated against `{xsd_file_path}`")

    else:
        # Handle the case when the payment_initiation_message_type is
        # not valid
        print(
            "Error: Invalid XML message type:",
            payment_initiation_message_type,
        )
        sys.exit(1)
