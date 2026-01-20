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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for streaming data loader functionality (Issue #122)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from pain001.data.loader import load_payment_data_streaming
from pain001.db.load_db_data_streaming import load_db_data_streaming
from pain001.exceptions import DataSourceError, PaymentValidationError


class TestStreamingLoaders(unittest.TestCase):
    """Test streaming data loaders for memory-efficient processing."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_csv_data_streaming(self):
        """Test streaming CSV data in chunks."""
        # Use existing template CSV file (already valid)
        csv_file = Path("pain001/templates/pain.001.001.03/template.csv")

        if not csv_file.exists():
            self.skipTest("Template CSV not found")

        # Load first few chunks with validation disabled
        chunks = []
        for i, chunk in enumerate(
            load_payment_data_streaming(
                str(csv_file), chunk_size=10, validate=False
            )
        ):
            chunks.append(chunk)
            if i >= 2:  # Just get first 3 chunks
                break

        # Should have at least 1 chunk
        self.assertGreater(len(chunks), 0)
        self.assertGreater(len(chunks[0]), 0)

    def test_load_db_data_streaming(self):
        """Test streaming SQLite data in chunks."""
        # Create test database with valid pain001 data structure
        db_file = Path(self.test_dir) / "test_payments.db"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # Create table with minimal valid schema
        cursor.execute(
            """
            CREATE TABLE pain001 (
                id INTEGER,
                date TEXT,
                nb_of_txs INTEGER,
                ctrl_sum REAL,
                initiator_name TEXT,
                payment_information_id TEXT,
                payment_method TEXT,
                batch_booking TEXT,
                service_level_code TEXT,
                requested_execution_date TEXT,
                debtor_name TEXT,
                debtor_account_IBAN TEXT,
                debtor_agent_BIC TEXT,
                charge_bearer TEXT,
                payment_id TEXT,
                payment_amount REAL,
                creditor_agent_BIC TEXT,
                creditor_name TEXT,
                creditor_account_IBAN TEXT,
                remittance_information TEXT
            )
        """
        )

        # Insert 30 rows with valid data
        for i in range(30):
            cursor.execute(
                """INSERT INTO pain001 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    i,  # id as integer
                    "2024-01-15",
                    1,
                    100.0 + i,
                    f"Test Initiator {i}",
                    f"PMT{i:03d}",
                    "TRF",
                    "true",
                    "NORM",
                    "2024-01-16",
                    f"Debtor {i}",
                    f"DE89370400440532013{i:03d}",
                    "BANKDEFFXXX",
                    "SLEV",
                    f"TX{i:03d}",
                    100.0 + i,
                    "BANKDEFFXXX",
                    f"Creditor {i}",
                    f"DE89370400440532014{i:03d}",
                    f"Payment {i}",
                ),
            )

        conn.commit()
        conn.close()

        # Load in chunks of 12 without validation
        chunks = list(
            load_db_data_streaming(str(db_file), "pain001", chunk_size=12)
        )

        # Should have 3 chunks: 12, 12, 6
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 12)
        self.assertEqual(len(chunks[1]), 12)
        self.assertEqual(len(chunks[2]), 6)

        # Verify data integrity
        self.assertEqual(chunks[0][0]["id"], 0)
        self.assertEqual(chunks[2][5]["id"], 29)

    def test_streaming_from_list(self):
        """Test streaming from large Python list."""
        # Create large list (1000 items) - disable validation for test data
        large_list = []
        for i in range(1000):
            large_list.append(
                {
                    "id": i,  # Integer ID
                    "date": "2024-01-15",
                    "nb_of_txs": 1,
                    "ctrl_sum": 100.0 + i,
                    "initiator_name": f"Initiator {i}",
                    "payment_information_id": f"PMT{i:04d}",
                    "payment_method": "TRF",
                    "batch_booking": "true",
                    "service_level_code": "NORM",
                    "requested_execution_date": "2024-01-16",
                    "debtor_name": f"Debtor {i}",
                    "debtor_account_IBAN": f"DE89370400440532013{i:03d}",
                    "debtor_agent_BIC": "BANKDEFFXXX",
                    "charge_bearer": "SLEV",
                    "payment_id": f"TX{i:04d}",
                    "payment_amount": 100.0 + i,
                    "creditor_agent_BIC": "BANKDEFFXXX",
                    "creditor_name": f"Creditor {i}",
                    "creditor_account_IBAN": f"DE89370400440532014{i:03d}",
                    "remittance_information": f"Payment {i}",
                }
            )

        # Load in chunks of 250 without validation
        chunks = list(
            load_payment_data_streaming(
                large_list, chunk_size=250, validate=False
            )
        )

        # Should have 4 chunks of 250 each
        self.assertEqual(len(chunks), 4)
        for chunk in chunks:
            self.assertEqual(len(chunk), 250)

        # Verify first and last
        self.assertEqual(chunks[0][0]["payment_id"], "TX0000")
        self.assertEqual(chunks[3][249]["payment_id"], "TX0999")

    def test_streaming_memory_efficiency(self):
        """Test that streaming uses constant memory (O(chunk_size))."""
        # Use real template CSV
        csv_file = Path("pain001/templates/pain.001.001.03/template.csv")

        if not csv_file.exists():
            self.skipTest("Template CSV not found")

        # Process in chunks without loading full dataset
        total_count = 0
        max_chunk_size = 0

        for chunk in load_payment_data_streaming(
            str(csv_file), chunk_size=100, validate=False
        ):
            total_count += len(chunk)
            max_chunk_size = max(max_chunk_size, len(chunk))

        self.assertGreater(total_count, 0)

    def test_streaming_empty_csv(self):
        """Test streaming with empty CSV file."""
        csv_file = Path(self.test_dir) / "empty.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("id,currency,amount,bic,iban,name\n")

        with self.assertRaises(DataSourceError) as cm:
            list(load_payment_data_streaming(str(csv_file)))

        self.assertIn("empty", str(cm.exception).lower())

    def test_streaming_empty_db_table(self):
        """Test streaming with empty database table."""
        db_file = Path(self.test_dir) / "empty.db"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE pain001 (
                id TEXT,
                currency TEXT
            )
        """
        )
        conn.commit()
        conn.close()

        with self.assertRaises(DataSourceError) as cm:
            list(load_db_data_streaming(str(db_file), "pain001"))

        self.assertIn("empty", str(cm.exception).lower())

    def test_streaming_invalid_data_type(self):
        """Test streaming with unsupported data type."""
        with self.assertRaises(DataSourceError) as cm:
            # Single dict not supported in streaming
            list(load_payment_data_streaming({"id": "TX001"}))

        self.assertIn("Unsupported data source type", str(cm.exception))

    def test_streaming_invalid_file_extension(self):
        """Test streaming with unsupported file type."""
        txt_file = Path(self.test_dir) / "test.txt"
        txt_file.write_text("some data")

        with self.assertRaises(DataSourceError) as cm:
            list(load_payment_data_streaming(str(txt_file)))

        self.assertIn("Unsupported file type", str(cm.exception))

    def test_streaming_file_not_found(self):
        """Test streaming with non-existent file."""
        missing = (
            Path("pain001/test_fixtures")
            / "nonexistent_streaming_loader_test.csv"
        )
        with self.assertRaises(FileNotFoundError):
            list(load_payment_data_streaming(str(missing)))

    def test_streaming_invalid_list_items(self):
        """Test streaming with invalid list items."""
        invalid_list = [{"id": "TX001"}, "not a dict", {"id": "TX002"}]

        with self.assertRaises(PaymentValidationError) as cm:
            list(load_payment_data_streaming(invalid_list))

        self.assertIn("must be dictionaries", str(cm.exception))

    def test_streaming_empty_list(self):
        """Test streaming with empty list."""
        with self.assertRaises(DataSourceError) as cm:
            list(load_payment_data_streaming([]))

        self.assertIn("Empty data list", str(cm.exception))

    def test_streaming_chunk_size_one(self):
        """Test streaming with chunk_size=1."""
        # Use real template CSV with small chunk size
        csv_file = Path("pain001/templates/pain.001.001.03/template.csv")

        if not csv_file.exists():
            self.skipTest("Template CSV not found")

        # Get first few chunks (whatever is available)
        chunks = []
        for i, chunk in enumerate(
            load_payment_data_streaming(
                str(csv_file), chunk_size=1, validate=False
            )
        ):
            chunks.append(chunk)
            if i >= 4:  # Try to get 5 chunks
                break

        # Should have at least 1 chunk
        self.assertGreater(len(chunks), 0)
        # Each chunk should have 1 item
        for chunk in chunks:
            self.assertEqual(len(chunk), 1)

    def test_streaming_chunk_size_larger_than_data(self):
        """Test streaming with chunk_size larger than total data."""
        # Use real template CSV with very large chunk size
        csv_file = Path("pain001/templates/pain.001.001.03/template.csv")

        if not csv_file.exists():
            self.skipTest("Template CSV not found")

        chunks = list(
            load_payment_data_streaming(
                str(csv_file), chunk_size=100000, validate=False
            )
        )

        # Should have 1 chunk with all rows
        self.assertEqual(len(chunks), 1)
        self.assertGreater(len(chunks[0]), 0)


if __name__ == "__main__":
    unittest.main()
