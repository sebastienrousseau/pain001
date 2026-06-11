# Copyright (C) 2023-2026 Sebastien Rousseau.
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
from datetime import datetime
from typing import Any

from pain001.csv.validate_csv_data import _validate_field_type

logger = logging.getLogger(__name__)

# Core required fields with expected types — kept in type parity with
# the CSV validator so a row passes or fails identically regardless of
# the data source it was loaded from.
REQUIRED_COLUMNS: dict[str, type] = {
    "id": int,
    "date": datetime,
    "nb_of_txs": int,
    "initiator_name": str,
    "payment_information_id": str,
    "payment_method": str,
    "debtor_name": str,
    "debtor_account_IBAN": str,
    "payment_amount": float,
    "currency": str,
    "creditor_name": str,
    "creditor_account_IBAN": str,
}


def validate_db_data(data: list[dict[str, Any]]) -> bool:
    """
    Validate the data from a database.

    Args:
        data (list of dict): The data to validate.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    for row in data:
        for column, data_type in REQUIRED_COLUMNS.items():
            if column not in row or row[column] is None or row[column] == "":
                logger.error(
                    "Error: Missing value for required column '%s' in row: %s",
                    column,
                    row,
                )
                return False
            value = str(row[column]).strip()
            if not _validate_field_type(value, data_type):
                logger.error(
                    "Error: Invalid %s value for column '%s' in row: %s",
                    data_type.__name__,
                    column,
                    row,
                )
                return False
    return True
