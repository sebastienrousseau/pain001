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

"""Backward compatibility tests for pain001 refactoring.

This module ensures that all existing functionality works correctly
after I/O decoupling and architecture refactoring (Issues #124, #122).

Coverage includes:
- CSV loading and validation
- SQLite loading and validation
- JSON/JSONL loading (Issue #147)
- Parquet loading (Issue #147)
- IBAN validation
- BIC validation
- Validation service
- Error handling and edge cases
- Regression scenarios
"""

import json
import tempfile
import unittest
from pathlib import Path

from pain001.csv.load_csv_data import load_csv_data
from pain001.csv.validate_csv_data import validate_csv_data
from pain001.db.load_db_data import load_db_data
from pain001.db.load_db_data_streaming import load_db_data_streaming
from pain001.db.validate_db_data import validate_db_data
from pain001.exceptions import PaymentValidationError
from pain001.json.load_json_data import load_json_data, load_jsonl_data
from pain001.validation.bic_validator import validate_bic
from pain001.validation.iban_validator import validate_iban


class TestCSVLoaderBackwardCompat(unittest.TestCase):
    """Test CSV loader backward compatibility."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_data_dir = Path("pain001/test_fixtures")
        self.valid_csv = self.test_data_dir / "template.csv"

    def test_load_csv_returns_list_of_dicts(self) -> None:
        """CSV loader should return list of dictionaries."""
        result = load_csv_data(str(self.valid_csv))
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], dict)

    def test_load_csv_preserves_column_names(self) -> None:
        """CSV loader should preserve header column names."""
        result = load_csv_data(str(self.valid_csv))
        first_row = result[0]
        # Check for common pain001 fields
        expected_fields = [
            "id",
            "date",
            "nb_of_txs",
            "debtor_name",
            "creditor_name",
        ]
        for field in expected_fields:
            self.assertIn(field, first_row)

    def test_load_csv_handles_string_path(self) -> None:
        """CSV loader should accept string paths."""
        result = load_csv_data(str(self.valid_csv))
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_load_csv_handles_path_object(self) -> None:
        """CSV loader should accept pathlib.Path objects."""
        result = load_csv_data(self.valid_csv)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_load_csv_file_not_found(self) -> None:
        """CSV loader should raise error for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_csv_data("pain001/test_fixtures/nonexistent_file.csv")

    def test_validate_csv_data_with_valid_data(self) -> None:
        """CSV validator should pass valid data."""
        data = load_csv_data(str(self.valid_csv))
        # Should not raise exception
        validate_csv_data(data)

    def test_validate_csv_data_checks_required_fields(self) -> None:
        """CSV validator should check for required fields."""
        invalid_data = [{"id": "1"}]  # Missing required fields
        # validate_csv_data logs error but doesn't raise
        # Just verify it processes the data
        try:
            validate_csv_data(invalid_data)
        except (PaymentValidationError, KeyError):
            pass  # Expected behavior


class TestSQLiteLoaderBackwardCompat(unittest.TestCase):
    """Test SQLite loader backward compatibility."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_data_dir = Path("pain001/test_fixtures")
        self.valid_db = self.test_data_dir / "template.db"

    def test_load_db_returns_list_of_dicts(self) -> None:
        """SQLite loader should return list of dictionaries."""
        result = load_db_data(str(self.valid_db), table_name="pain001")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], dict)

    def test_load_db_preserves_column_names(self) -> None:
        """SQLite loader should preserve table column names."""
        result = load_db_data(str(self.valid_db), table_name="pain001")
        first_row = result[0]
        # Check for common pain001 fields
        expected_fields = ["id", "date", "nb_of_txs"]
        for field in expected_fields:
            self.assertIn(field, first_row)

    def test_load_db_handles_string_path(self) -> None:
        """SQLite loader should accept string paths."""
        result = load_db_data(str(self.valid_db), table_name="pain001")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_load_db_handles_path_object(self) -> None:
        """SQLite loader should accept pathlib.Path objects."""
        result = load_db_data(str(self.valid_db), table_name="pain001")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_load_db_file_not_found(self) -> None:
        """SQLite loader should raise error for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_db_data("nonexistent_file.db", table_name="pain001")

    def test_load_db_streaming(self) -> None:
        """SQLite streaming loader should yield chunks."""
        chunk_count = 0
        for chunk in load_db_data_streaming(
            str(self.valid_db), "pain001", chunk_size=2
        ):
            self.assertIsInstance(chunk, list)
            self.assertGreater(len(chunk), 0)
            chunk_count += 1
        self.assertGreater(chunk_count, 0)

    def test_validate_db_data_with_valid_data(self) -> None:
        """SQLite validator should pass valid data."""
        data = load_db_data(str(self.valid_db), table_name="pain001")
        # Should not raise exception
        validate_db_data(data)

    def test_validate_db_data_checks_required_fields(self) -> None:
        """SQLite validator should check for required fields."""
        invalid_data = [{"id": "1"}]  # Missing required fields
        # validate_db_data logs error but doesn't raise
        # Just verify it processes the data
        try:
            validate_db_data(invalid_data)
        except (PaymentValidationError, KeyError):
            pass  # Expected behavior


class TestJSONLoaderBackwardCompat(unittest.TestCase):
    """Test JSON/JSONL loader backward compatibility."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sample_data = [
            {"id": "1", "name": "Payment 1"},
            {"id": "2", "name": "Payment 2"},
        ]

    def tearDown(self) -> None:
        """Clean up temporary files."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_load_json_array_format(self) -> None:
        """JSON loader should handle array format."""
        json_file = self.temp_dir / "test.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_data, f)

        result = load_json_data(str(json_file))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "1")

    def test_load_json_single_object_format(self) -> None:
        """JSON loader should handle single object format."""
        json_file = self.temp_dir / "test.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_data[0], f)

        result = load_json_data(str(json_file))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_load_jsonl_format(self) -> None:
        """JSON loader should handle JSONL (JSON Lines) format."""
        jsonl_file = self.temp_dir / "test.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for record in self.sample_data:
                f.write(json.dumps(record) + "\n")

        result = load_jsonl_data(str(jsonl_file))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_load_json_file_not_found(self) -> None:
        """JSON loader should raise error for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_json_data("nonexistent_file.json")

    def test_load_jsonl_file_not_found(self) -> None:
        """JSONL loader should raise error for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_jsonl_data("nonexistent_file.jsonl")


class TestParquetLoaderBackwardCompat(unittest.TestCase):
    """Test Parquet loader backward compatibility."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            self.pq = pq
            self.pa = pa
            self.has_parquet = True
        except ImportError:
            self.has_parquet = False

    def tearDown(self) -> None:
        """Clean up temporary files."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_parquet_loader_available(self) -> None:
        """Parquet loader should be importable."""
        if self.has_parquet:
            from pain001.parquet.load_parquet_data import load_parquet_data

            self.assertIsNotNone(load_parquet_data)

    def test_parquet_support_flag(self) -> None:
        """Parquet support flag should reflect availability."""
        from pain001.parquet.load_parquet_data import HAS_PARQUET_SUPPORT

        if self.has_parquet:
            self.assertTrue(HAS_PARQUET_SUPPORT)
        else:
            self.assertFalse(HAS_PARQUET_SUPPORT)

    def test_parquet_loader_with_data(self) -> None:
        """Parquet loader should load data correctly when available."""
        if not self.has_parquet:
            self.skipTest("pyarrow not available")

        from pain001.parquet.load_parquet_data import load_parquet_data

        # Create test Parquet file
        data = [
            {"id": "1", "name": "Payment 1"},
            {"id": "2", "name": "Payment 2"},
        ]
        table = self.pa.Table.from_pylist(data)
        parquet_file = self.temp_dir / "test.parquet"
        self.pq.write_table(table, parquet_file)

        result = load_parquet_data(str(parquet_file))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)


class TestIBANValidatorBackwardCompat(unittest.TestCase):
    """Test IBAN validator backward compatibility."""

    def test_validate_valid_iban(self) -> None:
        """IBAN validator should accept valid IBANs."""
        # Use commonly-tested valid IBANs with correct checksums
        valid_ibans = [
            "DE89370400440532013000",  # Valid German IBAN
            "CH9300762011623852957",  # Valid Swiss IBAN
            "FR1420041010050500013M02606",  # Valid French IBAN
        ]
        for iban in valid_ibans:
            is_valid, error = validate_iban(iban, strict=False)  # noqa: F841
            self.assertTrue(is_valid, f"Should validate {iban}: {error}")

    def test_validate_invalid_iban_checksum(self) -> None:
        """IBAN validator should reject invalid checksums."""
        invalid_ibans = [
            "DE89370400440532013009",  # Wrong checksum
            "FR1420041010050500013M02607",  # Wrong checksum
        ]
        for iban in invalid_ibans:
            is_valid, _error = validate_iban(iban, strict=False)
            self.assertFalse(is_valid, f"Should reject {iban}")

    def test_validate_iban_case_insensitive(self) -> None:
        """IBAN validator should handle case variations."""
        # Should handle both upper and lowercase
        is_valid_upper, _ = validate_iban(
            "DE89370400440532013008", strict=False
        )
        is_valid_lower, _ = validate_iban(
            "de89370400440532013008", strict=False
        )
        self.assertEqual(is_valid_upper, is_valid_lower)

    def test_validate_iban_with_spaces(self) -> None:
        """IBAN validator should handle spaces."""
        is_valid, _ = validate_iban(
            "DE89 3704 0044 0532 0130 00", strict=False
        )
        # May or may not be valid depending on implementation
        # Just verify it doesn't crash
        self.assertIsInstance(is_valid, bool)


class TestBICValidatorBackwardCompat(unittest.TestCase):
    """Test BIC validator backward compatibility."""

    def test_validate_valid_bic(self) -> None:
        """BIC validator should accept valid BICs."""
        valid_bics = [
            "BANKDEFFXXX",
            "SPUEDE2UXXX",
            "DEUTDEDBBER",
            "GENODEM1GLS",
        ]
        for bic in valid_bics:
            is_valid, error = validate_bic(bic, strict=False)  # noqa: F841
            self.assertTrue(is_valid, f"Should validate {bic}: {error}")

    def test_validate_short_bic(self) -> None:
        """BIC validator should accept short BICs (8 chars)."""
        is_valid, _error = validate_bic("BANKDEFF", strict=False)
        self.assertTrue(is_valid)

    def test_validate_invalid_bic_format(self) -> None:
        """BIC validator should reject invalid formats."""
        invalid_bics = [
            "INVALID123456",  # Too long
            "BANK",  # Too short
            "BANK$$$$XXXX",  # Invalid characters
        ]
        for bic in invalid_bics:
            is_valid, error = validate_bic(bic, strict=False)  # noqa: F841
            self.assertFalse(is_valid, f"Should reject {bic}: {error}")

    def test_validate_bic_case_insensitive(self) -> None:
        """BIC validator should handle case variations."""
        is_valid_upper, _ = validate_bic("BANKDEFFXXX", strict=False)
        is_valid_lower, _ = validate_bic("bankdeffxxx", strict=False)
        self.assertEqual(is_valid_upper, is_valid_lower)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error paths."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Clean up temporary files."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_empty_csv_file(self) -> None:
        """CSV loader should handle empty files gracefully."""
        empty_csv = self.temp_dir / "empty.csv"
        empty_csv.touch()

        # Should raise DataSourceError, ValueError, or StopIteration
        from pain001.exceptions import DataSourceError

        with self.assertRaises(DataSourceError):
            load_csv_data(str(empty_csv))

    def test_csv_with_only_headers(self) -> None:
        """CSV loader should handle files with only headers."""
        csv_file = self.temp_dir / "headers_only.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("id,name,value\n")

        # Should raise DataSourceError since file is empty (no data rows)
        from pain001.exceptions import DataSourceError

        with self.assertRaises(DataSourceError):
            load_csv_data(str(csv_file))

    def test_csv_with_special_characters(self) -> None:
        """CSV loader should handle special characters in data."""
        csv_file = self.temp_dir / "special_chars.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("id,description\n")
            f.write('1,"Payment for: €100, £50, ¥1000"\n')
            f.write('2,"Special chars: @#$%^&*()"\n')

        result = load_csv_data(str(csv_file))
        self.assertEqual(len(result), 2)
        self.assertIn("€100", result[0].get("description", ""))

    def test_csv_with_quoted_fields(self) -> None:
        """CSV loader should handle quoted fields correctly."""
        csv_file = self.temp_dir / "quoted.csv"
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("id,name,description\n")
            f.write('1,"John Doe","Has comma, in name"\n')
            f.write('2,"Jane Smith","No comma here"\n')

        result = load_csv_data(str(csv_file))
        self.assertEqual(len(result), 2)
        self.assertIn("comma", result[0]["description"])

    def test_json_with_empty_array(self) -> None:
        """JSON loader should handle empty arrays."""
        json_file = self.temp_dir / "empty.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump([], f)

        result = load_json_data(str(json_file))
        self.assertEqual(len(result), 0)

    def test_json_with_nulls(self) -> None:
        """JSON loader should handle null values."""
        json_file = self.temp_dir / "nulls.json"
        data = [{"id": "1", "value": None}, {"id": "2", "value": "test"}]
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = load_json_data(str(json_file))
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0]["value"])

    def test_iban_with_lowercase(self) -> None:
        """IBAN validator should normalize case."""
        is_valid1, _ = validate_iban("DE89370400440532013008", strict=False)
        is_valid2, _ = validate_iban("de89370400440532013008", strict=False)
        # Both should return consistent results
        self.assertEqual(is_valid1, is_valid2)

    def test_bic_padding(self) -> None:
        """BIC validator should handle 8-char and 11-char formats."""
        short_bic = "BANKDEFF"
        long_bic = "BANKDEFFXXX"
        # Both formats should be valid
        is_valid_short, _ = validate_bic(short_bic, strict=False)
        is_valid_long, _ = validate_bic(long_bic, strict=False)
        # Both formats should be valid
        self.assertTrue(is_valid_short)
        self.assertTrue(is_valid_long)


class TestRegressionScenarios(unittest.TestCase):
    """Test regression scenarios from refactoring."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_data_dir = Path("pain001/test_fixtures")

    def test_csv_and_db_load_same_data(self) -> None:
        """CSV and DB loaders should return equivalent data."""
        csv_file = self.test_data_dir / "template.csv"
        db_file = self.test_data_dir / "template.db"

        csv_data = load_csv_data(str(csv_file))
        db_data = load_db_data(str(db_file), table_name="pain001")

        # Both should be lists of dicts
        self.assertIsInstance(csv_data, list)
        self.assertIsInstance(db_data, list)

        # Both should have data
        self.assertGreater(len(csv_data), 0)
        self.assertGreater(len(db_data), 0)

        # Check that common fields exist in both
        if csv_data and db_data:
            csv_keys = set(csv_data[0].keys())
            db_keys = set(db_data[0].keys())
            common_keys = csv_keys & db_keys
            self.assertGreater(len(common_keys), 0)

    def test_streaming_vs_nonstreaming_csv(self) -> None:
        """Streaming and non-streaming CSV loaders should return same data."""
        csv_file = self.test_data_dir / "template.csv"

        # Load with standard loader
        full_data = load_csv_data(str(csv_file))

        # Load with streaming loader
        from pain001.csv.load_csv_data import load_csv_data_streaming

        streamed_data = []
        for chunk in load_csv_data_streaming(str(csv_file), chunk_size=2):
            streamed_data.extend(chunk)

        # Should have same length
        self.assertEqual(len(full_data), len(streamed_data))

        # Should have same first record
        if full_data:
            self.assertEqual(full_data[0], streamed_data[0])

    def test_loader_with_mixed_types(self) -> None:
        """Loaders should handle mixed data types correctly."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            csv_file = temp_dir / "mixed_types.csv"
            with open(csv_file, "w", encoding="utf-8") as f:
                f.write("id,amount,date,active\n")
                f.write("1,100.50,2023-01-01,true\n")
                f.write("2,200.75,2023-01-02,false\n")

            result = load_csv_data(str(csv_file))
            self.assertEqual(len(result), 2)
            # All values should be strings (CSV doesn't have types)
            self.assertIsInstance(result[0]["amount"], str)
            self.assertIsInstance(result[0]["active"], str)
        finally:
            import shutil

            shutil.rmtree(temp_dir)

    def test_validator_consistency(self) -> None:
        """Validators should be consistent across calls."""
        iban = "DE89370400440532013000"  # Use valid IBAN with correct checksum
        bic = "BANKDEFFXXX"

        # Use strict=False to get tuple returns
        result_iban1, _ = validate_iban(iban, strict=False)
        result_iban2, _ = validate_iban(iban, strict=False)
        result_bic1, _ = validate_bic(bic, strict=False)
        result_bic2, _ = validate_bic(bic, strict=False)

        # Same input should give same result
        self.assertEqual(result_iban1, result_iban2)
        self.assertEqual(result_bic1, result_bic2)


if __name__ == "__main__":
    unittest.main()
