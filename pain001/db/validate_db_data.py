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

from typing import Any

from pain001.csv.validate_csv_data import row_issues, validate_csv_data
from pain001.exceptions import RowIssue


def db_row_issues(
    data: list[dict[str, Any]],
    message_type: str | None = None,
    first_line: int = 1,
) -> list[RowIssue]:
    """Return the required-column problems in database rows.

    The same contract as :func:`~pain001.csv.validate_csv_data.row_issues`,
    except that an empty table is not an issue here: it never was for a
    database, and generation refuses it later.

    Args:
        data: The rows, one dictionary per row.
        message_type: The target message type, or ``None``.
        first_line: The record number of ``data[0]``, counted from 1.

    Returns:
        The issues in row order; empty when every row is valid.
    """
    return row_issues(data, message_type, first_line) if data else []


def validate_db_data(
    data: list[dict[str, Any]], message_type: str | None = None
) -> bool:
    """
    Validate the data from a database.

    The columns and types come from :func:`required_columns`, the same
    contract the CSV validator enforces, and problems are logged by row
    and column, never by value. An empty table passes.

    Args:
        data: The rows to validate, one dictionary per row.
        message_type: The target message type, e.g. ``pain.001.001.09``,
            or ``None`` when it is not yet known.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    return not data or validate_csv_data(data, message_type)
