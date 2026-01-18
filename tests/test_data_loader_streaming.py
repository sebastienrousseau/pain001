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

"""Tests for data loader streaming functionality."""

from pathlib import Path

import pytest

from pain001.data.loader import load_payment_data_streaming
from pain001.exceptions import DataSourceError, PaymentValidationError


class TestStreamPaymentData:
    """Test streaming payment data from various sources."""

    def test_stream_csv_data(self, tmp_path):
        """Test streaming CSV data in chunks."""
        csv_file = tmp_path / "stream_test.csv"
        # Create a CSV with multiple rows
        rows = [
            "id,date,nb_of_txs,initiator_name,payment_information_id,payment_method,batch_booking,service_level_code,requested_execution_date,debtor_name,debtor_account_IBAN,debtor_agent_BIC,forwarding_agent_BIC,charge_bearer,payment_id,payment_amount,currency,creditor_agent_BIC,creditor_name,creditor_account_IBAN,remittance_information,ctrl_sum"
        ]
        for i in range(10):
            rows.append(
                f"{i},2023-01-01,1,Init{i},PMT{i},TRF,false,SEPA,2023-01-15,Debtor{i},DE89370400440532013000,BICCODE,FWDBIC,DEBT,PAY{i},100.00,EUR,BICCODE,Creditor{i},DE89370400440532013000,Ref{i},100.00"
            )
        csv_file.write_text("\n".join(rows) + "\n")

        # Stream with chunk size of 3
        chunks = list(load_payment_data_streaming(str(csv_file), chunk_size=3))

        assert len(chunks) > 0
        # Should have multiple chunks since we have 10 rows
        assert len(chunks) >= 3

        # Each chunk should be a list of dicts
        for chunk in chunks:
            assert isinstance(chunk, list)
            for row in chunk:
                assert isinstance(row, dict)
                assert "id" in row

    def test_stream_nonexistent_file(self):
        """Test streaming from nonexistent file raises error."""
        missing = (
            Path("pain001/test_fixtures") / "nonexistent_streaming_test.csv"
        )
        with pytest.raises((FileNotFoundError, DataSourceError)):
            list(load_payment_data_streaming(str(missing), chunk_size=10))

    def test_stream_with_dict_list(self, tmp_path):
        """Test streaming from CSV file (list not directly supported)."""
        # The function expects file paths, not direct data
        # Create a CSV file instead
        csv_file = tmp_path / "list_test.csv"
        csv_file.write_text("id\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")

        chunks = list(
            load_payment_data_streaming(
                str(csv_file), chunk_size=3, validate=False
            )
        )

        assert (
            len(chunks) >= 3
        )  # At least 3 chunks for 10 rows with chunk_size=3
        assert all(isinstance(chunk, list) for chunk in chunks)

    def test_stream_csv_without_validation(self, tmp_path):
        """Test streaming CSV without validation."""
        csv_file = tmp_path / "no_validation.csv"
        csv_file.write_text("id\n1\n2\n3\n")

        # Should stream even with incomplete data when validation=False
        chunks = list(
            load_payment_data_streaming(
                str(csv_file), chunk_size=2, validate=False
            )
        )

        assert len(chunks) >= 1

    def test_stream_json_data(self, tmp_path):
        """Test streaming JSON data."""
        json_file = tmp_path / "test.json"
        data = [{"id": str(i), "name": f"Test{i}"} for i in range(5)]
        import json

        json_file.write_text(json.dumps(data))

        chunks = list(
            load_payment_data_streaming(
                str(json_file), chunk_size=2, validate=False
            )
        )

        assert len(chunks) >= 1
        assert all(isinstance(chunk, list) for chunk in chunks)

    def test_stream_db_data(self, tmp_path):
        """Test streaming database data."""
        db_file = tmp_path / "test.db"

        # Create a simple SQLite database
        import sqlite3

        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE pain001 (
                id TEXT,
                name TEXT
            )
        """
        )
        for i in range(5):
            cursor.execute(
                "INSERT INTO pain001 (id, name) VALUES (?, ?)",
                (str(i), f"Test{i}"),
            )
        conn.commit()
        conn.close()

        chunks = list(
            load_payment_data_streaming(
                str(db_file), chunk_size=2, validate=False
            )
        )

        assert len(chunks) >= 1
        assert all(isinstance(chunk, list) for chunk in chunks)

    def test_stream_parquet_data(self, tmp_path):
        """Test streaming Parquet data if pyarrow is available."""
        try:
            import pyarrow  # noqa: F401
            import pyarrow.parquet as pq  # noqa: F401

            parquet_file = tmp_path / "test.parquet"

            # Create test data
            import pandas as pd

            df = pd.DataFrame(
                {
                    "id": [str(i) for i in range(5)],
                    "name": [f"Test{i}" for i in range(5)],
                }
            )
            df.to_parquet(parquet_file)

            chunks = list(
                load_payment_data_streaming(
                    str(parquet_file), chunk_size=2, validate=False
                )
            )

            assert len(chunks) >= 1
            assert all(isinstance(chunk, list) for chunk in chunks)
        except ImportError:
            pytest.skip("pyarrow not available")

    def test_stream_jsonl_data(self, tmp_path):
        """Test streaming JSONL data."""
        jsonl_file = tmp_path / "test.jsonl"
        lines = [f'{{"id": "{i}", "name": "Test{i}"}}\n' for i in range(5)]
        jsonl_file.write_text("".join(lines))

        chunks = list(
            load_payment_data_streaming(
                str(jsonl_file), chunk_size=2, validate=False
            )
        )

        assert len(chunks) >= 1
        assert all(isinstance(chunk, list) for chunk in chunks)

    def test_stream_unsupported_file_type(self, tmp_path):
        """Test streaming with unsupported file type."""
        # Create a file with unsupported extension

        # Use tmp_path fixture instead of hardcoded /tmp
        unsupported_file = tmp_path / "test.unsupported"
        unsupported_file.write_text("invalid data", encoding="utf-8")

        with pytest.raises((DataSourceError, ValueError)):
            list(
                load_payment_data_streaming(
                    str(unsupported_file), chunk_size=10
                )
            )

    def test_stream_with_validation_failure(self, tmp_path):
        """Test streaming with validation enabled on invalid data."""
        csv_file = tmp_path / "invalid_structure.csv"
        csv_file.write_text("wrong_header\nvalue1\n")

        # Should raise validation error when validate=True
        with pytest.raises((PaymentValidationError, DataSourceError)):
            list(
                load_payment_data_streaming(
                    str(csv_file), chunk_size=10, validate=True
                )
            )
