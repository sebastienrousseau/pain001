# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Tests for pain001.validation.iban_validator module."""

import pytest

from pain001.exceptions import InvalidIBANError
from pain001.validation.iban_validator import (
    validate_iban,
    validate_iban_checksum,
    validate_iban_format,
    validate_iban_safe,
)


class TestIBANFormatValidation:
    """Test IBAN format validation (structure, not checksum)."""

    def test_valid_iban_format_germany(self):
        """Test valid German IBAN format."""
        is_valid, error = validate_iban_format("DE89370400440532013000")
        assert is_valid
        assert error == ""

    def test_valid_iban_format_austria(self):
        """Test valid Austrian IBAN format."""
        is_valid, _ = validate_iban_format("AT611904300234573201")
        assert is_valid

    def test_valid_iban_format_with_spaces(self):
        """Test IBAN format validation with spaces (should be removed)."""
        is_valid, _ = validate_iban_format("DE89 3704 0044 0532 0130 00")
        assert is_valid

    def test_iban_empty_string(self):
        """Test IBAN validation with empty string."""
        is_valid, error = validate_iban_format("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_iban_too_short(self):
        """Test IBAN validation with too short IBAN."""
        is_valid, error = validate_iban_format("DE89")
        assert not is_valid
        assert "length must be 15-34" in error

    def test_iban_too_long(self):
        """Test IBAN validation with too long IBAN."""
        is_valid, error = validate_iban_format("DE" + "1" * 40)
        assert not is_valid
        assert "length must be 15-34" in error

    def test_iban_invalid_country_code(self):
        """Test IBAN validation with invalid country code (numbers)."""
        is_valid, error = validate_iban_format("12893704004405320130")
        assert not is_valid
        assert "country code" in error.lower()

    def test_iban_invalid_check_digits(self):
        """Test IBAN validation with invalid check digits (letters)."""
        is_valid, error = validate_iban_format("DEXX3704004405320130")
        assert not is_valid
        assert "check digits" in error.lower()

    def test_iban_invalid_characters(self):
        """Test IBAN validation with invalid characters."""
        is_valid, error = validate_iban_format("DE89370400440532013@")
        assert not is_valid
        assert "alphanumeric" in error.lower()

    def test_iban_wrong_length_for_country(self):
        """Test IBAN validation with wrong length for specific country."""
        # German IBAN should be 22 characters, not 20
        is_valid, error = validate_iban_format("DE8937040044053201")
        assert not is_valid
        assert "length" in error.lower()
        assert "DE" in error


class TestIBANChecksumValidation:
    """Test IBAN checksum validation (ISO 7064 mod-97-10)."""

    def test_valid_iban_checksum_germany(self):
        """Test valid German IBAN checksum."""
        is_valid, error = validate_iban_checksum("DE89370400440532013000")
        assert is_valid
        assert error == ""

    def test_valid_iban_checksum_austria(self):
        """Test valid Austrian IBAN checksum."""
        is_valid, _ = validate_iban_checksum("AT611904300234573201")
        assert is_valid

    def test_valid_iban_checksum_france(self):
        """Test valid French IBAN checksum."""
        is_valid, _ = validate_iban_checksum("FR1420041010050500013M02606")
        assert is_valid

    def test_invalid_iban_checksum(self):
        """Test invalid IBAN checksum (wrong check digits)."""
        # Changed 89 to 00
        is_valid, error = validate_iban_checksum("DE00370400440532013000")
        assert not is_valid
        assert "checksum" in error.lower()
        assert "mod 97" in error.lower()

    def test_iban_checksum_with_spaces(self):
        """Test IBAN checksum validation with spaces."""
        is_valid, _ = validate_iban_checksum("DE89 3704 0044 0532 0130 00")
        assert is_valid

    def test_iban_checksum_invalid_character(self):
        """Test IBAN checksum validation with invalid character."""
        is_valid, error = validate_iban_checksum("DE89370400440532013@")
        assert not is_valid
        assert "Invalid character" in error


class TestIBANFullValidation:
    """Test complete IBAN validation (format + checksum)."""

    def test_validate_iban_strict_mode_valid(self):
        """Test IBAN validation in strict mode with valid IBAN."""
        is_valid, error = validate_iban("DE89370400440532013000", strict=True)
        assert is_valid
        assert error == ""

    def test_validate_iban_strict_mode_invalid_format(self):
        """Test IBAN validation in strict mode with invalid format."""
        with pytest.raises(InvalidIBANError) as exc_info:
            validate_iban("INVALID", strict=True)
        # Check that error message contains something meaningful
        assert exc_info.value.iban == "INVALID"
        assert exc_info.value.reason == "Invalid IBAN format"

    def test_validate_iban_strict_mode_invalid_checksum(self):
        """Test IBAN validation in strict mode with invalid checksum."""
        with pytest.raises(InvalidIBANError) as exc_info:
            validate_iban(
                "DE00370400440532013000", field="debtor_account", strict=True
            )
        assert exc_info.value.iban == "DE00370400440532013000"
        assert exc_info.value.field == "debtor_account"
        assert exc_info.value.reason is not None
        assert "checksum" in exc_info.value.reason.lower()

    def test_validate_iban_non_strict_mode_valid(self):
        """Test IBAN validation in non-strict mode with valid IBAN."""
        is_valid, error = validate_iban("DE89370400440532013000", strict=False)
        assert is_valid
        assert error == ""

    def test_validate_iban_non_strict_mode_invalid(self):
        """Test IBAN validation in non-strict mode with invalid IBAN."""
        is_valid, error = validate_iban("INVALID", strict=False)
        assert not is_valid
        assert error != ""

    def test_validate_iban_with_field_name(self):
        """Test IBAN validation with field name for error reporting."""
        with pytest.raises(InvalidIBANError) as exc_info:
            validate_iban("INVALID", field="creditor_account", strict=True)
        assert exc_info.value.field == "creditor_account"

    def test_validate_iban_safe_valid(self):
        """Test validate_iban_safe with valid IBAN."""
        assert validate_iban_safe("DE89370400440532013000")

    def test_validate_iban_safe_invalid(self):
        """Test validate_iban_safe with invalid IBAN."""
        assert not validate_iban_safe("INVALID")

    def test_validate_iban_safe_never_raises(self):
        """Test that validate_iban_safe never raises exceptions."""
        # Should not raise, just return False
        assert not validate_iban_safe("")
        assert not validate_iban_safe("INVALID")
        assert not validate_iban_safe("DE00370400440532013000")


class TestIBANCountryVariants:  # pylint: disable=too-few-public-methods
    """Test IBAN validation for various countries."""

    @pytest.mark.parametrize(
        "iban",
        [
            "DE89370400440532013000",  # Germany
            "AT611904300234573201",  # Austria
            "CH9300762011623852957",  # Switzerland
            "GB82WEST12345698765432",  # United Kingdom
            "FR1420041010050500013M02606",  # France
            "IT60X0542811101000000123456",  # Italy
            "ES9121000418450200051332",  # Spain
            "NL91ABNA0417164300",  # Netherlands
            "BE68539007547034",  # Belgium
        ],
    )
    def test_valid_ibans_various_countries(self, iban):
        """Test validation of valid IBANs from various countries."""
        is_valid, error = validate_iban(iban, strict=False)
        assert is_valid, f"Expected {iban} to be valid, but got error: {error}"


class TestIBANEdgeCases:
    """Test IBAN validation edge cases."""

    def test_iban_with_hyphens(self):
        """Test IBAN validation with hyphens (should be removed)."""
        is_valid, _ = validate_iban(
            "DE89-3704-0044-0532-0130-00", strict=False
        )
        assert is_valid

    def test_iban_lowercase(self):
        """Test IBAN validation with lowercase letters."""
        is_valid, _ = validate_iban("de89370400440532013000", strict=False)
        assert is_valid

    def test_iban_mixed_case(self):
        """Test IBAN validation with mixed case."""
        is_valid, _ = validate_iban("De89370400440532013000", strict=False)
        assert is_valid

    def test_iban_unknown_country_code(self):
        """Test IBAN with unknown country code (should not fail format check)."""
        # ZZ is not in known country codes, but format validation should pass
        # Only checksum validation would fail if the checksum is wrong
        is_valid, _ = validate_iban_format("ZZ8937040044053201300012")
        # Should pass format check (structure is valid)
        assert is_valid

    def test_iban_none_value(self):
        """Test IBAN validation with None value."""
        # None should cause an error when trying to call .replace()
        is_valid, error = validate_iban_format(None)  # type: ignore
        assert not is_valid
        assert "empty" in error.lower()

    def test_iban_checksum_invalid_character_error_path(self):
        """Test IBAN checksum with special character to trigger error branch."""
        is_valid, error = validate_iban_checksum("DE89370400440532013@")
        assert not is_valid
        assert "Invalid character" in error

    def test_iban_safe_with_field_parameter(self):
        """Test validate_iban_safe with field parameter (unused but API compatible)."""
        # Field parameter is accepted but not used
        assert validate_iban_safe("DE89370400440532013000", field="test_field")
