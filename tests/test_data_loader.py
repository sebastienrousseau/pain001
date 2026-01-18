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

"""Tests for the unified data loader."""

import csv
import sqlite3
from pathlib import Path

import pytest

from pain001.data.loader import load_payment_data
from pain001.exceptions import DataSourceError, PaymentValidationError


class TestDataLoader:
    """Test the universal data loader with various input sources."""

    @pytest.fixture
    def sample_payment_data(self):  # type: ignore
        """Sample payment data for testing with all required fields."""
        return [
            {
                "id": "1",
                "date": "2026-01-09T10:00:00.000Z",
                "nb_of_txs": "1",
                "ctrl_sum": "1000.00",
                "initiator_name": "Test Corp",
                "initiator_street_name": "Test Street",
                "initiator_building_number": "1",
                "initiator_postal_code": "12345",
                "initiator_town_name": "Test Town",
                "initiator_country_code": "DE",
                "payment_information_id": "PMT001",
                "payment_method": "TRF",
                "batch_booking": "true",
                "requested_execution_date": "2026-01-10T10:00:00.000Z",
                "debtor_name": "Debtor Corp",
                "debtor_street_name": "Debtor Street",
                "debtor_building_number": "2",
                "debtor_postal_code": "67890",
                "debtor_town_name": "Debtor Town",
                "debtor_country_code": "DE",
                "debtor_account_IBAN": "DE89370400440532013000",
                "debtor_agent_BIC": "BANKDEFFXXX",
                "charge_bearer": "SLEV",
                "payment_id": "TXN001",
                "payment_amount": "1000.00",
                "currency": "EUR",
                "payment_currency": "EUR",
                "creditor_agent_BIC": "SPUEDE2UXXX",
                "creditor_name": "Creditor Ltd",
                "creditor_street_name": "Creditor Street",
                "creditor_building_number": "3",
                "creditor_postal_code": "11223",
                "creditor_town_name": "Creditor Town",
                "creditor_country_code": "DE",
                "creditor_account_IBAN": "DE68210501700024690959",
                "purpose_code": "OTHR",
                "reference_number": "INV-2026-001",
                "reference_date": "2026-01-08T10:00:00.000Z",
                "service_level_code": "SEPA",
                "forwarding_agent_BIC": "SPUEDE2UXXX",
                "remittance_information": "Invoice Payment",
                "charge_account_IBAN": "DE89370400440532013000",
                "end_to_end_id": "TXN001",
                "payment_instruction_id": "PMT001",  # For SQLite validation
                "instruction_id": "INSTR001",  # For SQLite validation
                # Optional fields for DB validation
                "category_purpose": "",
                "remittance_info_unstructured": "",
                "remittance_info_structured": "",
                "addtl_end_to_end_id": "",
                "payment_info_structured": "",
            }
        ]

    @pytest.fixture
    def csv_file(self, sample_payment_data, tmp_path):  # type: ignore
        """Create temporary CSV file."""
        csv_path = tmp_path / "test_data.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=sample_payment_data[0].keys()
            )
            writer.writeheader()
            writer.writerows(sample_payment_data)
        return str(csv_path)

    @pytest.fixture
    def sqlite_file(self, sample_payment_data, tmp_path) -> None:
        """Create temporary SQLite file."""
        db_path = tmp_path / "test_data.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table
        fields = list(sample_payment_data[0].keys())
        create_sql = f"CREATE TABLE pain001 ({', '.join([f'{k} TEXT' for k in fields])})"
        cursor.execute(create_sql)

        # Insert data
        placeholders = ", ".join(["?" for _ in fields])
        insert_sql = f"INSERT INTO pain001 VALUES ({placeholders})"  # nosec B608 - static test SQL
        for row in sample_payment_data:
            cursor.execute(insert_sql, list(row.values()))

        conn.commit()
        conn.close()
        return str(db_path)

    # ========== BACKWARD COMPATIBILITY TESTS ==========

    def test_load_from_csv_file(self, csv_file) -> None:
        """Test loading from CSV file (existing functionality)."""
        data = load_payment_data(csv_file)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"
        assert data[0]["initiator_name"] == "Test Corp"

    def test_load_from_sqlite_file(self, sqlite_file) -> None:
        """Test loading from SQLite file (existing functionality)."""
        data = load_payment_data(sqlite_file)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"
        assert data[0]["initiator_name"] == "Test Corp"

    def test_file_not_found_error(self) -> None:
        """Test that FileNotFoundError is raised for missing files."""
        # Use a path in CWD to pass path validation, but fail existence check
        missing_file = (
            Path("pain001/test_fixtures") / "nonexistent_data_loader_test.csv"
        )
        # Ensure it really doesn't exist
        if missing_file.exists():
            missing_file.unlink()

        with pytest.raises(FileNotFoundError):
            load_payment_data(str(missing_file))

    def test_unsupported_file_type(self) -> None:
        """Test that DataSourceError is raised for unsupported file types."""
        with pytest.raises(DataSourceError, match="Unsupported file type"):
            load_payment_data("data.txt")

    def test_load_from_json_file(self, sample_payment_data, tmp_path) -> None:
        """Test loading from JSON file (new feature)."""
        import json

        json_file = tmp_path / "payments.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(sample_payment_data, f)

        data = load_payment_data(str(json_file))

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"
        assert data[0]["payment_amount"] == "1000.00"

    def test_load_from_jsonl_file(self, sample_payment_data, tmp_path) -> None:
        """Test loading from JSONL file (new feature)."""
        import json

        jsonl_file = tmp_path / "payments.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for record in sample_payment_data:
                f.write(json.dumps(record) + "\n")

        data = load_payment_data(str(jsonl_file))

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"

    @pytest.mark.skipif(
        not pytest.importorskip("pyarrow", reason="pyarrow not installed"),
        reason="pyarrow not installed",
    )
    def test_load_from_parquet_file(
        self, sample_payment_data, tmp_path
    ) -> None:
        """Test loading from Parquet file (new feature, requires pyarrow)."""
        pa = None  # Initialize to satisfy CodeQL
        pq = None
        try:
            import pyarrow as pa  # type: ignore[import-untyped,no-redef]
            import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
        except ImportError:
            pytest.skip("pyarrow not available")

        parquet_file = tmp_path / "payments.parquet"
        table = pa.Table.from_pylist(sample_payment_data)
        pq.write_table(table, str(parquet_file))

        data = load_payment_data(str(parquet_file))

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"

    # ========== NEW FEATURE TESTS ==========

    def test_load_from_list_of_dicts(self, sample_payment_data) -> None:
        """Test loading from Python list of dictionaries (new feature)."""
        data = load_payment_data(sample_payment_data)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "1"
        assert data[0]["initiator_name"] == "Test Corp"

    def test_load_from_single_dict(self, sample_payment_data) -> None:
        """Test loading from single Python dictionary (new feature)."""
        # Use first item from sample_payment_data fixture (which is a list)
        single_payment = sample_payment_data[0].copy()
        single_payment["id"] = "2"  # Change ID to distinguish from fixture

        data = load_payment_data(single_payment)

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "2"
        assert data[0]["initiator_name"] == "Test Corp"

    def test_load_multiple_payments_from_list(
        self, sample_payment_data
    ) -> None:
        """Test loading multiple payments from list."""
        # Create multiple copies of valid payment data
        base_payment = sample_payment_data[0].copy()
        payments = []
        for i in range(1, 6):
            payment = base_payment.copy()
            payment["id"] = str(i)
            payment["payment_id"] = f"PMT{i:03d}"
            payment["initiator_name"] = f"Corp {i}"
            payments.append(payment)

        data = load_payment_data(payments)

        assert isinstance(data, list)
        assert len(data) == 5
        assert data[0]["id"] == "1"
        assert data[4]["id"] == "5"

    def test_empty_list_raises_error(self) -> None:
        """Test that empty list raises DataSourceError."""
        with pytest.raises(DataSourceError, match="Empty data list"):
            load_payment_data([])

    def test_empty_dict_raises_error(self) -> None:
        """Test that empty dict raises DataSourceError."""
        with pytest.raises(DataSourceError, match="Empty data dictionary"):
            load_payment_data({})

    def test_list_with_non_dict_raises_error(self) -> None:
        """Test that list with non-dict items raises PaymentValidationError."""
        invalid_data = [{"id": "MSG001"}, "not a dict", {"id": "MSG003"}]

        with pytest.raises(
            PaymentValidationError,
            match="All items in data list must be dictionaries",
        ):
            load_payment_data(invalid_data)

    def test_unsupported_type_raises_error(self) -> None:
        """Test that unsupported data types raise DataSourceError."""
        with pytest.raises(
            DataSourceError, match="Unsupported data source type"
        ):
            load_payment_data(12345)

        with pytest.raises(
            DataSourceError, match="Unsupported data source type"
        ):
            load_payment_data(None)

    # ========== INTEGRATION TESTS ==========

    def test_data_equivalence_csv_vs_dict(
        self, csv_file, sample_payment_data
    ) -> None:
        """Test that CSV and dict sources produce equivalent data."""
        data_from_csv = load_payment_data(csv_file)
        data_from_dict = load_payment_data(sample_payment_data)

        # Compare values (ignoring potential type differences)
        assert len(data_from_csv) == len(data_from_dict)
        for csv_row, dict_row in zip(data_from_csv, data_from_dict):
            for key in csv_row.keys():
                assert str(csv_row[key]) == str(dict_row[key])

    def test_data_equivalence_sqlite_vs_dict(
        self, sqlite_file, sample_payment_data
    ) -> None:
        """Test that SQLite and dict sources produce equivalent data."""
        data_from_db = load_payment_data(sqlite_file)
        data_from_dict = load_payment_data(sample_payment_data)

        # Compare values
        assert len(data_from_db) == len(data_from_dict)
        for db_row, dict_row in zip(data_from_db, data_from_dict):
            for key in db_row.keys():
                assert str(db_row[key]) == str(dict_row[key])

    def test_load_from_list_with_validation_failure(self) -> None:
        """Test _load_from_list when validation fails (line 127)."""
        from unittest.mock import patch

        invalid_data_list = [{"id": "test", "date": "2023-01-01"}]

        with patch(
            "pain001.data.loader.validate_csv_data",
            autospec=True,
            return_value=False,
        ):
            with pytest.raises(
                PaymentValidationError, match="Data list validation failed"
            ):
                load_payment_data(invalid_data_list)

    def test_load_from_dict_with_validation_failure(self) -> None:
        """Test _load_from_dict when validation fails (line 143)."""
        from unittest.mock import patch

        invalid_data_dict = {"id": "test", "date": "2023-01-01"}

        with patch(
            "pain001.data.loader.validate_csv_data",
            autospec=True,
            return_value=False,
        ):
            with pytest.raises(
                PaymentValidationError,
                match="Data dictionary validation failed",
            ):
                load_payment_data(invalid_data_dict)
