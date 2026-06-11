# Copyright (C) 2023-2026 Pain001. All rights reserved.
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

"""Validate CSV payment data against required-field rules."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _redact_row_for_error(row: dict[str, Any]) -> dict[str, str]:
    """Return a log-safe copy of a payment row for validation errors."""
    redacted: dict[str, str] = {}
    for key, value in row.items():
        text = "" if value is None else str(value)
        key_lower = key.lower()

        if "iban" in key_lower or "account" in key_lower:
            redacted[key] = _mask_value(text, 4)
        elif "bic" in key_lower:
            redacted[key] = _mask_value(text, 3)
        elif "name" in key_lower:
            redacted[key] = "[REDACTED]"
        elif "remittance" in key_lower or "reference" in key_lower:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = text
    return redacted


def _mask_value(value: str, visible_chars: int) -> str:
    """Mask a sensitive value while keeping a small prefix and suffix."""
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}****{value[-visible_chars:]}"


def _validate_datetime(value: str) -> bool:
    """Validate datetime field.

    Args:
        value: The datetime string to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    # Handle the "Z" suffix for UTC
    cleaned_value = value
    if value.endswith("Z"):
        cleaned_value = value[:-1] + "+00:00"
    try:
        datetime.fromisoformat(cleaned_value)
        return True
    except ValueError:
        try:
            datetime.strptime(cleaned_value, "%Y-%m-%d")
            return True
        except ValueError:
            return False


def _validate_field_type(value: str, data_type: type) -> bool:
    """Validate a single field against its expected type.

    Args:
        value: The field value to validate.
        data_type: The expected data type.

    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        if data_type is int:
            int(value)
        elif data_type is float:
            float(value)
        elif data_type is bool:
            if value.lower() not in ("true", "false", "0", "1"):
                return False
        elif data_type is datetime:
            return _validate_datetime(value)
        # str type always passes if not empty
        return True
    except ValueError:
        return False


def _validate_row(
    row: dict[str, Any], required_columns: dict[str, type]
) -> tuple[list[str], list[str]]:
    """Validate a single row of CSV data.

    Args:
        row: A dictionary containing row data.
        required_columns: Dictionary of required column names and types.

    Returns:
        tuple: (missing_columns, invalid_columns)
    """
    missing_columns = []
    invalid_columns = []

    for column, data_type in required_columns.items():
        raw_value = row.get(column)

        if raw_value is None:
            missing_columns.append(column)
            continue

        # Non-file sources (JSON, SQLite, Python dicts) carry native
        # types (int/float/bool); coerce to str so one type-check
        # path serves every loader.
        value = str(raw_value).strip()

        if not value:
            missing_columns.append(column)
            continue

        # Validate type
        if not _validate_field_type(value, data_type):
            invalid_columns.append(column)

    return missing_columns, invalid_columns


def _format_errors(
    row: dict[str, Any],
    missing_columns: list[str],
    invalid_columns: list[str],
    required_columns: dict[str, type],
) -> list[str]:
    """Format error messages for a row.

    Args:
        row: The row with errors.
        missing_columns: List of missing column names.
        invalid_columns: List of invalid column names.
        required_columns: Dictionary of required column types.

    Returns:
        list: List of formatted error messages.
    """
    errors = []
    safe_row = _redact_row_for_error(row)
    if missing_columns:
        errors.append(
            f"Error: Missing value(s) for column(s) {missing_columns} in row: {safe_row}"
        )
    if invalid_columns:
        expected_types = [
            required_columns[col].__name__ for col in invalid_columns
        ]
        errors.append(
            f"Error: Invalid data type for column(s) "
            f"{invalid_columns}, expected {expected_types} in row: {safe_row}"
        )
    return errors


def validate_csv_data(data: list[dict[str, Any]]) -> bool:
    """Validate the CSV data before processing it.

    Args:
        data: A list of dictionaries containing the CSV data.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    required_columns = {
        "id": int,
        "date": datetime,
        "nb_of_txs": int,
        "ctrl_sum": float,
        "initiator_name": str,
        "payment_information_id": str,
        "payment_method": str,
        "batch_booking": bool,
        "service_level_code": str,
        "requested_execution_date": datetime,
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

    if not data:
        logger.error("The CSV data is empty.")
        return False

    is_valid = True
    all_errors = []  # Batch error messages for better performance

    for row in data:
        missing_columns, invalid_columns = _validate_row(row, required_columns)

        if missing_columns or invalid_columns:
            is_valid = False
            all_errors.extend(
                _format_errors(
                    row, missing_columns, invalid_columns, required_columns
                )
            )

    if all_errors:
        logger.error("\n".join(all_errors))

    return is_valid
