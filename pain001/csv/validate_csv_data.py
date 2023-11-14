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

# Validate the CSV data before processing it. The CSV data must contain
# the following columns:
#
# - id (int) - unique identifier
# - date (str) - date of the payment
# - nb_of_txs (int) - number of transactions
# - initiator_name (str) - name of the initiator
# - payment_information_id (str) - payment information identifier
# - payment_method (str) - payment method
# - batch_booking (bool) - batch booking
# - ctrl_sum (int) - control sum
# - service_level_code (str) - service level code
# - requested_execution_date (str) - requested execution date
# - debtor_name (str) - debtor name
# - debtor_account_IBAN (str) - debtor account IBAN
# - debtor_agent_BIC (str) - debtor agent BIC
# - forwarding_agent_BIC (str) - forwarding agent BIC
# - charge_bearer (str) - charge bearer
# - payment_id (str) - payment identifier
# - payment_amount (str) - payment amount
# - currency (str) - currency
# - creditor_agent_BIC (str) - creditor agent BIC
# - creditor_name (str) - creditor name
# - creditor_account_IBAN (str) - creditor account IBAN
# - remittance_information (str) - remittance information


def validate_csv_data(data):
    """Validate the CSV data before processing it.

    Args:
        data (list): A list of dictionaries containing the CSV data.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    required_columns = {
        "id": int,
        "date": str,
        "nb_of_txs": int,
        "ctrl_sum": str,
        "initiator_name": str,
        "payment_information_id": str,
        "payment_method": str,
        "batch_booking": bool,
        "service_level_code": str,
        "requested_execution_date": str,
        "debtor_name": str,
        "debtor_account_IBAN": str,
        "debtor_agent_BIC": str,
        "forwarding_agent_BIC": str,
        "charge_bearer": str,
        "payment_id": str,
        "payment_amount": float,
        "currency": str,
        "creditor_agent_BIC": str,
        "creditor_name": str,
        "creditor_account_IBAN": str,
        "remittance_information": str,
    }

    for row in data:
        for column, data_type in required_columns.items():
            value = row.get(column)
            if value is None or value.strip() == "":
                print(
                    f"Error: Missing value for column '{column}' "
                    f"in row: {row}"
                )
                return False

            try:
                if data_type == int:
                    int(value)
                elif data_type == float:
                    float(value)
                elif data_type == bool:
                    if value.lower() not in ["true", "false"]:
                        raise ValueError
                else:
                    str(value)
            except ValueError:
                print(
                    f"Error: Invalid data type for column '{column}', "
                    f"expected {data_type.__name__} in row: {row}"
                )
                return False

    return True
