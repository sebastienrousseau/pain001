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

from pain001.exceptions import IssueCode, RowIssue, format_issues
from pain001.schemas.required_columns import required_columns

logger = logging.getLogger(__name__)

#: Code and message for a value that is not of its column's type.
_TYPE_ISSUES: dict[type, tuple[str, str]] = {
    int: (IssueCode.NOT_INTEGER, "not a whole number"),
    float: (IssueCode.NOT_DECIMAL, "not a decimal number"),
    bool: (IssueCode.NOT_BOOLEAN, "not true, false, 1 or 0"),
    datetime: (IssueCode.NOT_DATE, "not a date (YYYY-MM-DD or ISO 8601)"),
}


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


def _issues_for_row(
    row: dict[str, Any], required: dict[str, type], line: int
) -> list[RowIssue]:
    """Return the issues in one row: missing values first, then types.

    Args:
        row: The row.
        required: Required column names and types.
        line: The row's line in the input, counted from 1.

    Returns:
        One issue per bad column, in column order within each group.
    """
    missing, invalid = _validate_row(row, required)
    issues = [
        RowIssue(line, column, IssueCode.MISSING_VALUE, "missing value")
        for column in missing
    ]
    for column in invalid:
        code, message = _TYPE_ISSUES[required[column]]
        issues.append(RowIssue(line, column, code, message))
    return issues


def row_issues(
    data: list[dict[str, Any]],
    message_type: str | None = None,
    first_line: int = 1,
) -> list[RowIssue]:
    """Return every required-column problem in ``data``, by line.

    The columns and types come from :func:`required_columns`: the
    bundled JSON schema of ``message_type`` when given, otherwise every
    column all bundled schemas describe. No issue carries the value.

    Args:
        data: The payment rows.
        message_type: The target message type, or ``None``.
        first_line: The line of ``data[0]`` in the input: 2 for a CSV
            file (its header is line 1), 1 for other inputs, more for a
            later chunk.

    Returns:
        The issues in input order; empty when every row is valid.
    """
    if not data:
        return [
            RowIssue(
                None,
                None,
                IssueCode.EMPTY_INPUT,
                "the input has no payment rows",
            )
        ]
    required = required_columns(message_type)
    return [
        issue
        for index, row in enumerate(data)
        for issue in _issues_for_row(row, required, first_line + index)
    ]


def validate_csv_data(
    data: list[dict[str, Any]], message_type: str | None = None
) -> bool:
    """Validate payment rows against the required-column contract.

    :func:`row_issues` lists the problems; this logs them (by line and
    column, never by value) and answers yes or no.

    Args:
        data: A list of dictionaries containing the CSV data.
        message_type: The target message type, e.g. ``pain.001.001.09``,
            or ``None`` when it is not yet known.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    issues = row_issues(data, message_type)
    if issues:
        logger.error(
            "Payment rows failed validation:%s", format_issues(issues)
        )
    return not issues
