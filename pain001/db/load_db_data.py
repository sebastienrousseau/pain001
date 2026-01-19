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
#
# CodeQL: This module uses parameterized queries where possible.
# For table names (which cannot be parameterized), we use strict allowlist validation
# via enable_sanitize_table_name() to prevent SQL injection (CWE-89).

import os
import re
import sqlite3
from typing import Any

from pain001.exceptions import ConfigurationError
from pain001.security import validate_path


def sanitize_table_name(table_name: str) -> str:
    """
    Validate and sanitize a table name to prevent SQL injection.
    Uses strict validation: only alphanumeric characters and underscores allowed.
    MUST start with a letter (SQL identifier rules).

    Args:
        table_name (str): The table name to validate.

    Returns:
        str: The validated table name (unchanged if valid).

    Raises:
        ConfigurationError: If the table name is empty or contains invalid characters.
    """

    if not table_name:
        raise ConfigurationError("Table name cannot be empty")

    # Strict validation: only alphanumeric and underscore, must start with letter
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", table_name):
        raise ConfigurationError(
            f"Invalid table name '{table_name}'. "
            "Table names must start with a letter and contain only "
            "alphanumeric characters and underscores."
        )

    return table_name


def load_db_data(data_file_path: str, table_name: str) -> list[dict[str, Any]]:
    """
    Load data from an SQLite database table into a list of dictionaries.

    Args:
        data_file_path (str): The path to the SQLite database file.
        table_name (str): The name of the table from which data will be loaded.

    Returns:
        list:
            A list of dictionaries where each dictionary represents a row of
            data.
            The keys in each dictionary correspond to the column names, and the
            values are the column values for that row.

    Raises:
        FileNotFoundError:
            If the SQLite file specified by data_file_path does not exist.
        sqlite3.OperationalError:
            If there is an issue with SQLite database operations.

    Example:
        data = load_db_data("my_database.db", "my_table")
    """

    # Validate path to prevent traversal attacks

    try:
        # must_exist=True ensures both validation and existence check
        safe_path = validate_path(
            data_file_path,
            must_exist=True,
        )  # nosec B108 - Returns sanitized string
    except Exception as e:
        raise FileNotFoundError(
            f"SQLite file path validation failed: {data_file_path}"
        ) from e

    # Check file existence using os.path for string path
    if not os.path.isfile(safe_path):
        raise FileNotFoundError(
            f"SQLite file '{data_file_path}' does not exist."
        )

    # Connect to the SQLite database (now safe after validation)
    conn = sqlite3.connect(str(safe_path))  # nosec B108
    try:
        cursor = conn.cursor()

        # Validate the table_name before using it in the query (strict regex validation)
        table_name = sanitize_table_name(table_name)

        # Fetch column names from the table
        # Safe: table_name validated via regex to contain only [a-zA-Z0-9_]
        cursor.execute(f"PRAGMA table_info({table_name})")  # nosec B608
        columns = [column[1] for column in cursor.fetchall()]

        # Use parameterised query to prevent SQL injection
        # Note: SQLite does not support ? placeholders for table names.
        # sanitize_table_name() enforces strict validation: ^[a-zA-Z][a-zA-Z0-9_]*$
        query = f"SELECT * FROM [{table_name}]"  # nosec B608 # CodeQL: py/sql-injection (Sanitized)
        cursor.execute(query)
        rows = cursor.fetchall()

        # Create a list of dictionaries with column names as keys
        data = []
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                row_dict[columns[i]] = value
            data.append(row_dict)

        return data
    finally:
        # Close the connection to the SQLite database
        conn.close()
