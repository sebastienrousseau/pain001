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


def validate_db_data(data):
    """Validate the SQLite data before processing it.

    Args:
        data (list): A list of dictionaries containing the SQLite data.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    required_columns = {
        "id": int,
        "date": str,
        "nb_of_txs": int,
        "initiator_name": str,
        "payment_information_id": str,
        "payment_method": str,
        "batch_booking": bool,
        "control_sum": int,
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
            if value is None or str(value).strip() == "":
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
                    if str(value).lower() not in ["true", "false"]:
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
