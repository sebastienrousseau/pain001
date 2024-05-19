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

import logging

# Configure the logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR)


def validate_db_data(data):
    """
    Validate the data from a database.

    Args:
        data (list of dict): The data to validate.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    required_columns = [
        "id",
        "date",
        "nb_of_txs",
        "initiator_name",
        "initiator_street_name",
        "initiator_building_number",
        "initiator_postal_code",
        "initiator_town_name",
        "initiator_country_code",
        "payment_information_id",
        "payment_method",
        "batch_booking",
        "requested_execution_date",
        "debtor_name",
        "debtor_street_name",
        "debtor_building_number",
        "debtor_postal_code",
        "debtor_town_name",
        "debtor_country_code",
        "debtor_account_IBAN",
        "debtor_agent_BIC",
        "charge_bearer",
        "payment_id",
        "payment_amount",
        "currency",
        "payment_currency",
        "ctrl_sum",
        "creditor_agent_BIC",
        "creditor_name",
        "creditor_street_name",
        "creditor_building_number",
        "creditor_postal_code",
        "creditor_town_name",
        "creditor_country_code",
        "creditor_account_IBAN",
        "purpose_code",
        "reference_number",
        "reference_date",
        "service_level_code",
        "end_to_end_id",
        "payment_instruction_id",
        "instruction_id",
        "category_purpose",
        "remittance_info_unstructured",
        "remittance_info_structured",
        "addtl_end_to_end_id",
        "payment_info_structured",
        "forwarding_agent_BIC",
        "remittance_information",
    ]

    for row in data:
        for column in required_columns:
            if column not in row or row[column] is None:
                logger.error(
                    "Error: Missing value for column '%s' in row: %s",
                    column,
                    row,
                )
                return False
    return True
