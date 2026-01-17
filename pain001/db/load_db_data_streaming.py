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

"""Memory-efficient streaming loader for SQLite database."""

import os
import sqlite3
from collections.abc import Generator
from typing import Any

from pain001.db.load_db_data import sanitize_table_name
from pain001.exceptions import DataSourceError


def load_db_data_streaming(
    data_file_path: str, table_name: str, chunk_size: int = 1000
) -> Generator[list[dict[str, Any]], None, None]:
    """Load data from SQLite database in chunks for memory-efficient processing.

    This function yields chunks of database rows instead of loading the entire
    table into memory, making it suitable for large databases.

    Args:
        data_file_path (str): The path to the SQLite database file.
        table_name (str): The name of the table from which data will be loaded.
        chunk_size (int): Number of rows to yield per chunk. Default is 1000.

    Yields:
        list: A list of dictionaries containing chunk_size rows of data.

    Raises:
        FileNotFoundError: If the SQLite file does not exist.
        sqlite3.OperationalError: If there is an issue with database operations.
        ValueError: If the table is empty or doesn't exist.

    Example:
        >>> for chunk in load_db_data_streaming('payments.db', 'pain001', chunk_size=500):
        ...     # Process chunk
        ...     process_payment_batch(chunk)

    Performance:
        - Memory usage: O(chunk_size) instead of O(table_rows)
        - Enables processing of tables larger than available RAM
        - Uses cursor fetching for efficient streaming
    """
    # Check if the SQLite file exists
    if not os.path.exists(data_file_path):
        raise FileNotFoundError(
            f"SQLite file '{data_file_path}' does not exist."
        )

    # Sanitize table name to prevent SQL injection
    # Validate the table_name before using it in the query (strict regex validation)
    table_name = sanitize_table_name(table_name)

    # Connect to the SQLite database
    conn = sqlite3.connect(data_file_path)
    try:
        cursor = conn.cursor()

        # Fetch column names from the table
        # Safe: table_name validated via regex to contain only [a-zA-Z0-9_]
        cursor.execute(f"PRAGMA table_info({table_name})")  # nosec B608
        columns_info = cursor.fetchall()

        if not columns_info:
            raise DataSourceError(
                f"Table '{table_name}' does not exist or has no columns."
            )

        columns = [column[1] for column in columns_info]

        # Use parameterized query to prevent SQL injection
        # Note: SQLite does not support ? placeholders for table names.
        # sanitize_table_name() enforces strict validation: ^[a-zA-Z][a-zA-Z0-9_]*$
        query = f"SELECT * FROM [{table_name}]"  # nosec B608
        cursor.execute(query)

        row_count = 0
        while True:
            # Fetch chunk_size rows
            rows = cursor.fetchmany(chunk_size)
            if not rows:
                break

            # Convert rows to list of dictionaries
            chunk: list[dict[str, Any]] = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    row_dict[columns[i]] = value
                chunk.append(row_dict)
                row_count += 1

            yield chunk

        if row_count == 0:
            raise DataSourceError(
                f"The table '{table_name}' in '{data_file_path}' is empty."
            )

    finally:
        # Close the connection to the SQLite database
        conn.close()
