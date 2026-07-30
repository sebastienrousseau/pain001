# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Validate SQLite payment data against required-field rules."""

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
        data: The rows to validate, one dictionary per row.

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
