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

import sqlite3
import os


def sanitize_table_name(table_name):
    """
    Sanitize a table name by replacing all characters that are not alphanumeric
    or underscores with underscores.

    Args:
        table_name (str): The table name to sanitize.

    Returns:
        str: The sanitized table name.
    """
    sanitized_name = ""
    for char in table_name:
        if char.isalnum() or char == "_":
            sanitized_name += char
        else:
            sanitized_name += "_"

    # Ensure the resulting name starts with an alphabetic character
    if not sanitized_name[0].isalpha():
        sanitized_name = "table_" + sanitized_name

    return sanitized_name


def load_db_data(data_file_path, table_name):
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

    # Check if the SQLite file exists
    if not os.path.exists(data_file_path):
        raise FileNotFoundError(
            f"SQLite file '{data_file_path}' does not exist."
        )

    # Connect to the SQLite database
    conn = sqlite3.connect(data_file_path)
    cursor = conn.cursor()

    # Sanitize the table_name before using it in the query
    table_name = sanitize_table_name(table_name)

    # Fetch column names from the table
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    # Sanitize the table_name before using it in the query
    table_name = sanitize_table_name(table_name)

    # Use string formatting to construct the query

    query = f"SELECT * FROM {table_name}"
    cursor.execute(query)
    rows = cursor.fetchall()

    # Create a list of dictionaries with column names as keys
    data = []
    for row in rows:
        row_dict = {}
        for i, value in enumerate(row):
            row_dict[columns[i]] = value
        data.append(row_dict)

    # Close the connection to the SQLite database
    conn.close()

    return data
