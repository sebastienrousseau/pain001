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


import sqlite3

import pytest

from pain001.db.load_db_data import load_db_data, sanitize_table_name
from pain001.exceptions import ConfigurationError


# Test sanitize_table_name function
def test_sanitize_table_name():
    """Test that valid table names pass strict validation."""
    assert sanitize_table_name("valid_table_name") == "valid_table_name"
    assert sanitize_table_name("ValidTableName") == "ValidTableName"
    assert sanitize_table_name("Table123") == "Table123"
    assert sanitize_table_name("table_name_123") == "table_name_123"


def test_sanitize_table_name_invalid() -> None:
    """Test that invalid table names raise ConfigurationError."""
    # Table name with spaces
    with pytest.raises(ConfigurationError, match="Invalid table name"):
        sanitize_table_name("invalid table name")

    # Table name starting with number
    with pytest.raises(ConfigurationError, match="Invalid table name"):
        sanitize_table_name("123invalidname")

    # Table name with special characters
    with pytest.raises(ConfigurationError, match="Invalid table name"):
        sanitize_table_name("table!@#name")


def test_sanitize_table_name_empty() -> None:
    """Test that sanitize_table_name raises ConfigurationError for empty string."""
    with pytest.raises(ConfigurationError, match="Table name cannot be empty"):
        sanitize_table_name("")


def test_sanitize_table_name_all_special_chars() -> None:
    """Test table name with all special characters raises error."""
    with pytest.raises(ConfigurationError, match="Invalid table name"):
        sanitize_table_name("!@#$%")


# Test load_db_data function
def test_load_db_data(tmp_path):
    # Create a temporary SQLite database
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create a test table and insert data
    cursor.execute(
        "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
    )
    cursor.execute("INSERT INTO test_table (name) VALUES ('Alice')")
    cursor.execute("INSERT INTO test_table (name) VALUES ('Bob')")
    conn.commit()
    conn.close()

    # Test loading data from the table
    data = load_db_data(db_file, "test_table")
    assert len(data) == 2
    assert data[0]["name"] == "Alice"
    assert data[1]["name"] == "Bob"

    # Test FileNotFoundError
    with pytest.raises(FileNotFoundError):
        load_db_data("non_existent.db", "test_table")

    # Test sqlite3.OperationalError for non-existent table
    with pytest.raises(sqlite3.OperationalError):
        load_db_data(db_file, "non_existent_table")


# If the script is executed directly, run the tests
if __name__ == "__main__":
    pytest.main()
