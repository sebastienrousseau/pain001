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

"""Tests for pain001.validation.bic_validator module."""

import pytest

from pain001.exceptions import InvalidBICError
from pain001.validation.bic_validator import (
    validate_bic,
    validate_bic_format,
    validate_bic_safe,
)


class TestBICFormatValidation:
    """Test BIC format validation."""

    def test_valid_bic_8_characters(self):
        """Test valid BIC with 8 characters."""
        is_valid, error = validate_bic_format("DEUTDEFF")
        assert is_valid
        assert error == ""

    def test_valid_bic_11_characters(self):
        """Test valid BIC with 11 characters (with branch code)."""
        is_valid, error = validate_bic_format("DEUTDEFF500")
        assert is_valid
        assert error == ""

    def test_valid_bic_with_spaces(self):
        """Test BIC validation with spaces (should be removed)."""
        is_valid, _ = validate_bic_format("DEUT DEFF")
        assert is_valid

    def test_bic_empty_string(self):
        """Test BIC validation with empty string."""
        is_valid, error = validate_bic_format("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_bic_wrong_length_7(self):
        """Test BIC validation with 7 characters (too short)."""
        is_valid, error = validate_bic_format("DEUTDEF")
        assert not is_valid
        assert "8 or 11" in error

    def test_bic_wrong_length_9(self):
        """Test BIC validation with 9 characters (invalid length)."""
        is_valid, error = validate_bic_format("DEUTDEFF5")
        assert not is_valid
        assert "8 or 11" in error

    def test_bic_wrong_length_10(self):
        """Test BIC validation with 10 characters (invalid length)."""
        is_valid, error = validate_bic_format("DEUTDEFF50")
        assert not is_valid
        assert "8 or 11" in error

    def test_bic_wrong_length_12(self):
        """Test BIC validation with 12 characters (too long)."""
        is_valid, error = validate_bic_format("DEUTDEFF5000")
        assert not is_valid
        assert "8 or 11" in error

    def test_bic_invalid_bank_code_with_numbers(self):
        """Test BIC with numbers in bank code (first 4 chars)."""
        is_valid, error = validate_bic_format("DEU1DEFF")
        assert not is_valid
        assert "bank code" in error.lower()
        assert "must be letters" in error

    def test_bic_invalid_country_code_with_numbers(self):
        """Test BIC with numbers in country code (chars 5-6)."""
        is_valid, error = validate_bic_format("DEUT1EFF")
        assert not is_valid
        assert "country code" in error.lower()

    def test_bic_invalid_country_code(self):
        """Test BIC with invalid country code."""
        is_valid, error = validate_bic_format("DEUTZZFF")
        assert not is_valid
        assert "ZZ" in error
        assert "not a valid" in error

    def test_bic_invalid_location_code_special_char(self):
        """Test BIC with special character in location code."""
        is_valid, error = validate_bic_format("DEUTDE@F")
        assert not is_valid
        assert "location code" in error.lower()
        assert "alphanumeric" in error

    def test_bic_invalid_branch_code_special_char(self):
        """Test BIC with special character in branch code."""
        is_valid, error = validate_bic_format("DEUTDEFF@00")
        assert not is_valid
        assert "branch code" in error.lower()
        assert "alphanumeric" in error


class TestBICFullValidation:
    """Test complete BIC validation."""

    def test_validate_bic_strict_mode_valid_8_chars(self):
        """Test BIC validation in strict mode with valid 8-char BIC."""
        is_valid, error = validate_bic("DEUTDEFF", strict=True)
        assert is_valid
        assert error == ""

    def test_validate_bic_strict_mode_valid_11_chars(self):
        """Test BIC validation in strict mode with valid 11-char BIC."""
        is_valid, error = validate_bic("DEUTDEFF500", strict=True)
        assert is_valid
        assert error == ""

    def test_validate_bic_strict_mode_invalid(self):
        """Test BIC validation in strict mode with invalid BIC."""
        with pytest.raises(InvalidBICError) as exc_info:
            validate_bic("INVALID", strict=True)
        assert "INVALID" in str(exc_info.value)
        assert exc_info.value.bic == "INVALID"

    def test_validate_bic_strict_mode_with_field(self):
        """Test BIC validation in strict mode with field name."""
        with pytest.raises(InvalidBICError) as exc_info:
            validate_bic("BADCODE", field="debtor_agent", strict=True)
        assert exc_info.value.bic == "BADCODE"
        assert exc_info.value.field == "debtor_agent"
        assert exc_info.value.reason is not None
        assert "ISO 9362" in exc_info.value.reason

    def test_validate_bic_non_strict_mode_valid(self):
        """Test BIC validation in non-strict mode with valid BIC."""
        is_valid, error = validate_bic("DEUTDEFF", strict=False)
        assert is_valid
        assert error == ""

    def test_validate_bic_non_strict_mode_invalid(self):
        """Test BIC validation in non-strict mode with invalid BIC."""
        is_valid, error = validate_bic("INVALID", strict=False)
        assert not is_valid
        assert error != ""

    def test_validate_bic_with_field_name(self):
        """Test BIC validation with field name for error reporting."""
        with pytest.raises(InvalidBICError) as exc_info:
            validate_bic("INVALID", field="creditor_agent", strict=True)
        assert exc_info.value.field == "creditor_agent"

    def test_validate_bic_safe_valid(self):
        """Test validate_bic_safe with valid BIC."""
        assert validate_bic_safe("DEUTDEFF")
        assert validate_bic_safe("DEUTDEFF500")

    def test_validate_bic_safe_invalid(self):
        """Test validate_bic_safe with invalid BIC."""
        assert not validate_bic_safe("INVALID")
        assert not validate_bic_safe("DEUTDE")  # Too short

    def test_validate_bic_safe_never_raises(self):
        """Test that validate_bic_safe never raises exceptions."""
        # Should not raise, just return False
        assert not validate_bic_safe("")
        assert not validate_bic_safe("INVALID")
        assert not validate_bic_safe("123")


class TestBICCountryVariants:  # pylint: disable=too-few-public-methods
    """Test BIC validation for various countries."""

    @pytest.mark.parametrize(
        "bic",
        [
            "DEUTDEFF",  # Germany (Deutsche Bank)
            "DEUTDEFF500",  # Germany with branch
            "RZBAATWW",  # Austria (Raiffeisen)
            "BNPAFRPP",  # France (BNP Paribas)
            "BARCGB22",  # United Kingdom (Barclays)
            "UBSWCHZH",  # Switzerland (UBS)
            "ABNANL2A",  # Netherlands (ABN AMRO)
            "BSCHESMM",  # Spain (Banco Santander)
            "BCITITMMXXX",  # Italy (Intesa Sanpaolo) with branch
            "CHASUS33",  # USA (Chase)
        ],
    )
    def test_valid_bics_various_countries(self, bic):
        """Test validation of valid BICs from various countries."""
        is_valid, error = validate_bic(bic, strict=False)
        assert is_valid, f"Expected {bic} to be valid, but got error: {error}"


class TestBICEdgeCases:
    """Test BIC validation edge cases."""

    def test_bic_with_hyphens(self):
        """Test BIC validation with hyphens (should be removed)."""
        is_valid, _ = validate_bic("DEUT-DEFF", strict=False)
        assert is_valid

    def test_bic_lowercase(self):
        """Test BIC validation with lowercase letters."""
        is_valid, _ = validate_bic("deutdeff", strict=False)
        assert is_valid

    def test_bic_mixed_case(self):
        """Test BIC validation with mixed case."""
        is_valid, _ = validate_bic("DeUtDeFf", strict=False)
        assert is_valid

    def test_bic_with_numbers_in_location_code(self):
        """Test BIC with numbers in location code (allowed)."""
        is_valid, _ = validate_bic("DEUTDE2F", strict=False)
        assert is_valid

    def test_bic_with_numbers_in_branch_code(self):
        """Test BIC with numbers in branch code (allowed)."""
        is_valid, _ = validate_bic("DEUTDEFF123", strict=False)
        assert is_valid

    def test_bic_all_uppercase(self):
        """Test BIC in all uppercase (standard format)."""
        is_valid, _ = validate_bic("DEUTDEFF500", strict=False)
        assert is_valid

    def test_bic_none_value(self):
        """Test BIC validation with None value."""
        # None should cause an error when trying to call .replace()
        is_valid, error = validate_bic_format(None)  # type: ignore
        assert not is_valid
        assert "empty" in error.lower()


class TestBICComparison:
    """Test BIC comparison and validation consistency."""

    def test_bic_8_vs_11_characters_same_bank(self):
        """Test that 8-char and 11-char BIC for same bank are both valid."""
        bic_8 = "DEUTDEFF"
        bic_11 = "DEUTDEFF500"

        assert validate_bic_safe(bic_8)
        assert validate_bic_safe(bic_11)

    def test_multiple_branch_codes_same_bank(self):
        """Test multiple branch codes for same bank."""
        assert validate_bic_safe("DEUTDEFF500")
        assert validate_bic_safe("DEUTDEFF600")
        assert validate_bic_safe("DEUTDEFFABC")
