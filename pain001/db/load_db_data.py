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

import sqlite3
import os


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
    if not os.path.exists(data_file_path):
        raise FileNotFoundError(
            f"SQLite file '{data_file_path}' does not exist."
        )

    conn = sqlite3.connect(data_file_path)
    cursor = conn.cursor()

    # Fetch column names from the table
    cursor.execute("PRAGMA table_info({})".format(table_name))
    columns = [column[1] for column in cursor.fetchall()]

    # Fetch data from the table using a parameterized query
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

    conn.close()

    return data
