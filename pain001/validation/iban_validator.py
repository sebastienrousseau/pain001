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

"""IBAN (International Bank Account Number) validator.

This module implements ISO 7064 mod-97-10 checksum validation for IBANs.
It validates both format and checksum integrity before XML generation,
significantly reducing bank rejection rates.

Example:
    >>> from pain001.validation.iban_validator import validate_iban
    >>>
    >>> # Valid IBAN
    >>> is_valid, error = validate_iban("DE89370400440532013000")
    >>> assert is_valid
    >>>
    >>> # Invalid checksum
    >>> is_valid, error = validate_iban("DE00370400440532013000")
    >>> assert not is_valid
    >>> assert "checksum" in error.lower()

Standards:
    - ISO 13616:2020 - International Bank Account Number (IBAN)
    - ISO 7064 - Check digit mod-97-10 algorithm
"""

from pain001.exceptions import InvalidIBANError

# SEPA IBAN lengths by country code (ISO 13616)
IBAN_LENGTHS = {
    "AD": 24,  # Andorra
    "AE": 23,  # United Arab Emirates
    "AL": 28,  # Albania
    "AT": 20,  # Austria
    "AZ": 28,  # Azerbaijan
    "BA": 20,  # Bosnia and Herzegovina
    "BE": 16,  # Belgium
    "BG": 22,  # Bulgaria
    "BH": 22,  # Bahrain
    "BR": 29,  # Brazil
    "BY": 28,  # Belarus
    "CH": 21,  # Switzerland
    "CR": 22,  # Costa Rica
    "CY": 28,  # Cyprus
    "CZ": 24,  # Czech Republic
    "DE": 22,  # Germany
    "DK": 18,  # Denmark
    "DO": 28,  # Dominican Republic
    "EE": 20,  # Estonia
    "EG": 29,  # Egypt
    "ES": 24,  # Spain
    "FI": 18,  # Finland
    "FO": 18,  # Faroe Islands
    "FR": 27,  # France
    "GB": 22,  # United Kingdom
    "GE": 22,  # Georgia
    "GI": 23,  # Gibraltar
    "GL": 18,  # Greenland
    "GR": 27,  # Greece
    "GT": 28,  # Guatemala
    "HR": 21,  # Croatia
    "HU": 28,  # Hungary
    "IE": 22,  # Ireland
    "IL": 23,  # Israel
    "IQ": 23,  # Iraq
    "IS": 26,  # Iceland
    "IT": 27,  # Italy
    "JO": 30,  # Jordan
    "KW": 30,  # Kuwait
    "KZ": 20,  # Kazakhstan
    "LB": 28,  # Lebanon
    "LC": 32,  # Saint Lucia
    "LI": 21,  # Liechtenstein
    "LT": 20,  # Lithuania
    "LU": 20,  # Luxembourg
    "LV": 21,  # Latvia
    "MC": 27,  # Monaco
    "MD": 24,  # Moldova
    "ME": 22,  # Montenegro
    "MK": 19,  # North Macedonia
    "MR": 27,  # Mauritania
    "MT": 31,  # Malta
    "MU": 30,  # Mauritius
    "NL": 18,  # Netherlands
    "NO": 15,  # Norway
    "PK": 24,  # Pakistan
    "PL": 28,  # Poland
    "PS": 29,  # Palestine
    "PT": 25,  # Portugal
    "QA": 29,  # Qatar
    "RO": 24,  # Romania
    "RS": 22,  # Serbia
    "SA": 24,  # Saudi Arabia
    "SE": 24,  # Sweden
    "SI": 19,  # Slovenia
    "SK": 24,  # Slovakia
    "SM": 27,  # San Marino
    "TN": 24,  # Tunisia
    "TR": 26,  # Turkey
    "UA": 29,  # Ukraine
    "VA": 22,  # Vatican City
    "VG": 24,  # British Virgin Islands
    "XK": 20,  # Kosovo
}


def validate_iban_format(
    iban: str,
) -> tuple[bool, str]:
    """Validate IBAN format structure.

    Checks:
    - Minimum 15 characters (shortest IBAN: Norway)
    - Maximum 34 characters (ISO 13616 limit)
    - First 2 characters are valid country code
    - Characters 3-4 are digits (check digits)
    - Remaining characters are alphanumeric
    - Length matches country-specific IBAN length

    Args:
        iban: IBAN string to validate (with or without spaces).

    Returns:
        Tuple of (is_valid, error_message).

    Example:
        >>> is_valid, error = validate_iban_format("DE89370400440532013000")
        >>> assert is_valid
    """
    if not iban:
        return False, "IBAN cannot be empty"

    # Remove spaces for validation
    iban_clean = iban.replace(" ", "").replace("-", "").upper()
    iban_len = len(iban_clean)

    # Check length range
    if not 15 <= iban_len <= 34:
        return (
            False,
            f"IBAN length must be 15-34 characters (got {iban_len})",
        )

    # Check all format requirements together
    country_ok = iban_clean[:2].isalpha()
    checkdigit_ok = iban_clean[2:4].isdigit()
    bban_ok = iban_clean[4:].isalnum()

    if not (country_ok and checkdigit_ok and bban_ok):
        errors = []
        if not country_ok:
            errors.append("must start with 2-letter country code")
        if not checkdigit_ok:
            errors.append("characters 3-4 must be check digits (00-99)")
        if not bban_ok:
            errors.append("must contain only alphanumeric characters")
        return False, f"IBAN format invalid: {'; '.join(errors)}"

    # Validate country-specific length
    country_code = iban_clean[:2]
    if (
        country_code in IBAN_LENGTHS
        and len(iban_clean) != IBAN_LENGTHS[country_code]
    ):
        return (
            False,
            f"Invalid IBAN length for {country_code}: "
            f"{len(iban_clean)} characters (expected {IBAN_LENGTHS[country_code]})",
        )
    else:
        # Country code not in known list - warn but don't fail
        # (allows for future IBAN countries)
        pass

    return True, ""


def validate_iban_checksum(iban: str) -> tuple[bool, str]:
    """Validate IBAN checksum using ISO 7064 mod-97-10 algorithm.

    Algorithm:
    1. Move first 4 characters to end: "DE89370400440532013000" → "370400440532013000DE89"
    2. Replace letters with numbers (A=10, B=11, ..., Z=35)
    3. Calculate mod 97 of resulting number
    4. Valid IBAN has mod 97 = 1

    Args:
        iban: IBAN string to validate (with or without spaces).

    Returns:
        Tuple of (is_valid, error_message).

    Example:
        >>> is_valid, error = validate_iban_checksum("DE89370400440532013000")
        >>> assert is_valid
    """
    # Remove spaces
    iban_clean = iban.replace(" ", "").replace("-", "").upper()

    # Move first 4 characters to end
    rearranged = iban_clean[4:] + iban_clean[:4]

    # Replace letters with numbers (A=10, B=11, ..., Z=35)
    numeric_iban = ""
    for char in rearranged:
        if char.isdigit():
            numeric_iban += char
        elif char.isalpha():
            # A=10, B=11, ..., Z=35
            numeric_iban += str(ord(char) - ord("A") + 10)
        else:
            return False, f"Invalid character in IBAN: {char}"

    # Calculate mod 97
    try:
        remainder = int(numeric_iban) % 97
    except ValueError as e:
        return False, f"Invalid numeric IBAN representation: {e}"

    if remainder != 1:
        return (
            False,
            f"IBAN checksum validation failed (mod 97 = {remainder}, expected 1)",
        )

    return True, ""


def validate_iban(
    iban: str, field: str | None = None, strict: bool = True
) -> tuple[bool, str]:
    """Validate IBAN format and checksum.

    This is the main entry point for IBAN validation. It performs both
    format validation and ISO 7064 mod-97-10 checksum verification.

    Args:
        iban: IBAN string to validate.
        field: Optional field name for error reporting.
        strict: If True, raise InvalidIBANError on failure. If False, return tuple.

    Returns:
        Tuple of (is_valid, error_message). If strict=True and invalid, raises exception.

    Raises:
        InvalidIBANError: If strict=True and IBAN is invalid.

    Example:
        >>> # Non-strict mode (returns tuple)
        >>> is_valid, error = validate_iban("DE89370400440532013000", strict=False)
        >>> assert is_valid
        >>>
        >>> # Strict mode (raises exception on error)
        >>> try:
        ...     validate_iban("DE00370400440532013000", field="debtor_account")
        ... except InvalidIBANError as e:
        ...     print(f"Invalid: {e}")
    """
    # Format validation
    is_valid, error = validate_iban_format(iban)
    if not is_valid:
        if strict:
            raise InvalidIBANError(
                message=error,
                iban=iban,
                field=field,
                reason="Invalid IBAN format",
            )
        return False, error

    # Checksum validation
    is_valid, error = validate_iban_checksum(iban)
    if not is_valid:
        if strict:
            raise InvalidIBANError(
                message=error,
                iban=iban,
                field=field,
                reason="Invalid IBAN checksum (ISO 7064 mod-97-10)",
            )
        return False, error

    return True, ""


def validate_iban_safe(iban: str, field: str | None = None) -> bool:
    """Validate IBAN and return True/False (never raises exceptions).

    This is a convenience wrapper for validate_iban with strict=False.
    Useful when you only need a boolean result without error details.

    Args:
        iban: IBAN string to validate.
        field: Optional field name (unused, for API compatibility).

    Returns:
        True if IBAN is valid, False otherwise.

    Example:
        >>> if validate_iban_safe("DE89370400440532013000"):
        ...     print("Valid IBAN")
    """
    is_valid, _ = validate_iban(iban, field=field, strict=False)
    return is_valid
