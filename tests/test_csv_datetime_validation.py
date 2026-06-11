# Copyright (C) 2023-2026 Pain001. All rights reserved.
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
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test coverage gaps to achieve 99%+ coverage."""

from pain001.csv.validate_csv_data import (
    _validate_datetime,
    _validate_field_type,
)


class TestCsvDateTimeValidation:
    """Test CSV datetime validation edge cases."""

    def test_validate_datetime_iso_date(self) -> None:
        """Test datetime validation with ISO date format."""
        assert _validate_datetime("2024-01-15") is True

    def test_validate_datetime_iso_datetime(self) -> None:
        """Test datetime validation with ISO datetime format."""
        assert _validate_datetime("2024-01-15T10:30:00") is True

    def test_validate_datetime_with_z_suffix(self) -> None:
        """Test datetime validation with Z (UTC) suffix."""
        assert _validate_datetime("2024-01-15T10:30:00Z") is True

    def test_validate_datetime_with_timezone(self) -> None:
        """Test datetime validation with timezone offset."""
        assert _validate_datetime("2024-01-15T10:30:00+01:00") is True

    def test_validate_datetime_invalid(self) -> None:
        """Test datetime validation with invalid format."""
        assert _validate_datetime("invalid-date") is False

    def test_validate_datetime_empty_string(self) -> None:
        """Test datetime validation with empty string."""
        assert _validate_datetime("") is False

    def test_validate_datetime_yyyy_mm_dd_format(self) -> None:
        """Test datetime validation with YYYY-MM-DD format (strptime fallback)."""
        # This specifically tests the strptime fallback path
        # when fromisoformat fails but YYYY-MM-DD format succeeds
        assert _validate_datetime("2024-12-25") is True
        assert _validate_datetime("1999-01-01") is True
        assert _validate_datetime("2026-06-15") is True


class TestCsvFieldTypeValidation:
    """Test CSV field type validation."""

    def test_field_type_validation_int_valid(self) -> None:
        """Test integer field validation with valid values."""
        assert _validate_field_type("12345", int) is True
        assert _validate_field_type("-999", int) is True
        assert _validate_field_type("0", int) is True

    def test_field_type_validation_int_invalid(self) -> None:
        """Test integer field validation with invalid values."""
        assert _validate_field_type("abc", int) is False
        assert _validate_field_type("12.5", int) is False

    def test_field_type_validation_float_valid(self) -> None:
        """Test float field validation with valid values."""
        assert _validate_field_type("123.45", float) is True
        assert _validate_field_type("0.5", float) is True
        assert _validate_field_type("-99.99", float) is True

    def test_field_type_validation_float_invalid(self) -> None:
        """Test float field validation with invalid values."""
        assert _validate_field_type("abc", float) is False
        assert _validate_field_type("12.34.56", float) is False

    def test_field_type_validation_str(self) -> None:
        """Test string field validation."""
        assert _validate_field_type("hello", str) is True
        assert _validate_field_type("", str) is True
        assert _validate_field_type("123", str) is True

    def test_field_type_validation_bool_valid(self) -> None:
        """Test boolean field validation with valid values."""
        assert _validate_field_type("true", bool) is True
        assert _validate_field_type("false", bool) is True
        assert _validate_field_type("True", bool) is True
        assert _validate_field_type("False", bool) is True
        # SQLite stores booleans as 0/1
        assert _validate_field_type("0", bool) is True
        assert _validate_field_type("1", bool) is True

    def test_field_type_validation_bool_invalid(self) -> None:
        """Test boolean field validation with invalid values."""
        assert _validate_field_type("yes", bool) is False
        assert _validate_field_type("2", bool) is False
        assert _validate_field_type("invalid", bool) is False
