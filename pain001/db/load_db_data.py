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

# Load the SQLite database into a list of dictionaries with the column names as
# keys


def load_db_data(data_file_path, table_name):
    if not os.path.exists(data_file_path):
        raise FileNotFoundError(
            f"SQLite file '{data_file_path}' does not exist."
        )

    conn = sqlite3.connect(data_file_path)
    cursor = conn.cursor()

    # Fetch column names from the table
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]

    # Fetch data from the table
    cursor.execute(f"SELECT * FROM {table_name}")
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
