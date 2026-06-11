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
# See the License for the specific language governing permissions and
# limitations under the License.

"""BIC (Business Identifier Code) / SWIFT Code validator.

This module implements ISO 9362 format validation for BIC/SWIFT codes.
It validates format structure to catch typos before XML generation.

Example:
    >>> from pain001.validation.bic_validator import validate_bic
    >>>
    >>> # Valid BIC (8 characters)
    >>> is_valid, error = validate_bic("DEUTDEFF")
    >>> assert is_valid
    >>>
    >>> # Valid BIC (11 characters with branch code)
    >>> is_valid, error = validate_bic("DEUTDEFF500")
    >>> assert is_valid
    >>>
    >>> # Invalid BIC (wrong length)
    >>> is_valid, error = validate_bic("DEUTDE")
    >>> assert not is_valid

Standards:
    - ISO 9362:2022 - Banking — Banking telecommunication messages — Business identifier code (BIC)
"""

from pain001.exceptions import InvalidBICError

# ISO 3166-1 alpha-2 country codes (SEPA + major financial centers)
VALID_COUNTRY_CODES = {
    "AD",
    "AE",
    "AL",
    "AR",
    "AT",
    "AU",
    "AZ",
    "BA",
    "BE",
    "BG",
    "BH",
    "BR",
    "BY",
    "CA",
    "CH",
    "CL",
    "CN",
    "CO",
    "CR",
    "CY",
    "CZ",
    "DE",
    "DK",
    "DO",
    "EE",
    "EG",
    "ES",
    "FI",
    "FO",
    "FR",
    "GB",
    "GE",
    "GI",
    "GL",
    "GR",
    "GT",
    "HK",
    "HR",
    "HU",
    "ID",
    "IE",
    "IL",
    "IN",
    "IQ",
    "IS",
    "IT",
    "JO",
    "JP",
    "KR",
    "KW",
    "KZ",
    "LB",
    "LC",
    "LI",
    "LT",
    "LU",
    "LV",
    "MC",
    "MD",
    "ME",
    "MK",
    "MR",
    "MT",
    "MU",
    "MX",
    "MY",
    "NL",
    "NO",
    "NZ",
    "PH",
    "PK",
    "PL",
    "PS",
    "PT",
    "QA",
    "RO",
    "RS",
    "RU",
    "SA",
    "SE",
    "SG",
    "SI",
    "SK",
    "SM",
    "TH",
    "TN",
    "TR",
    "TW",
    "UA",
    "US",
    "VA",
    "VG",
    "XK",
    "ZA",
}


def validate_bic_format(
    bic: str,
) -> tuple[bool, str]:
    """Validate BIC format structure according to ISO 9362.

    BIC Structure:
    - AAAABBCCXXX (11 characters) or AAAABBCC (8 characters)
    - AAAA: Bank code (4 letters, A-Z)
    - BB: Country code (2 letters, ISO 3166-1 alpha-2)
    - CC: Location code (2 alphanumeric, A-Z or 0-9)
    - XXX: Branch code (3 alphanumeric, optional)

    Args:
        bic: BIC/SWIFT code to validate (spaces removed automatically).

    Returns:
        Tuple of (is_valid, error_message).

    Example:
        >>> is_valid, error = validate_bic_format("DEUTDEFF")
        >>> assert is_valid
        >>> is_valid, error = validate_bic_format("DEUTDEFF500")
        >>> assert is_valid
    """
    if not bic:
        return False, "BIC cannot be empty"

    # Remove spaces and convert to uppercase
    bic_clean = bic.replace(" ", "").replace("-", "").upper()

    # Check length (must be 8 or 11)
    if len(bic_clean) not in [8, 11]:
        return (
            False,
            f"BIC must be 8 or 11 characters (got {len(bic_clean)}: '{bic_clean}')",
        )

    # Check all code formats together
    bank_code = bic_clean[:4]
    country_code = bic_clean[4:6]
    location_code = bic_clean[6:8]
    branch_code = bic_clean[8:11] if len(bic_clean) == 11 else ""

    bank_ok = bank_code.isalpha()
    country_ok = country_code.isalpha()
    location_ok = location_code.isalnum()
    branch_ok = branch_code.isalnum() if branch_code else True

    if not (bank_ok and country_ok and location_ok and branch_ok):
        errors = []
        if not bank_ok:
            errors.append(
                f"bank code (first 4 chars) must be letters (got '{bank_code}')"
            )
        if not country_ok:
            errors.append(
                f"country code (chars 5-6) must be letters (got '{country_code}')"
            )
        if not location_ok:
            errors.append(
                f"location code (chars 7-8) must be alphanumeric (got '{location_code}')"
            )
        if not branch_ok:
            errors.append(
                f"branch code (chars 9-11) must be alphanumeric (got '{branch_code}')"
            )
        return False, f"BIC format invalid: {'; '.join(errors)}"

    # Validate country code against known codes
    if country_code not in VALID_COUNTRY_CODES:
        return (
            False,
            f"BIC country code '{country_code}' is not a valid ISO 3166-1 alpha-2 code",
        )

    return True, ""


def validate_bic(
    bic: str, field: str | None = None, strict: bool = True
) -> tuple[bool, str]:
    """Validate BIC/SWIFT code format.

    This is the main entry point for BIC validation. It performs ISO 9362
    format validation.

    Args:
        bic: BIC/SWIFT code to validate.
        field: Optional field name for error reporting.
        strict: If True, raise InvalidBICError on failure. If False, return tuple.

    Returns:
        Tuple of (is_valid, error_message). If strict=True and invalid, raises exception.

    Raises:
        InvalidBICError: If strict=True and BIC is invalid.

    Example:
        >>> # Non-strict mode (returns tuple)
        >>> is_valid, error = validate_bic("DEUTDEFF", strict=False)
        >>> assert is_valid
        >>>
        >>> # Strict mode (raises exception on error)
        >>> try:
        ...     validate_bic("INVALID", field="debtor_agent")
        ... except InvalidBICError as e:
        ...     print(f"Invalid: {e}")
    """
    is_valid, error = validate_bic_format(bic)

    if not is_valid:
        if strict:
            raise InvalidBICError(
                message=error,
                bic=bic,
                field=field,
                reason="Invalid BIC format (ISO 9362)",
            )
        return False, error

    return True, ""


def validate_bic_safe(bic: str, field: str | None = None) -> bool:
    """Validate BIC and return True/False (never raises exceptions).

    This is a convenience wrapper for validate_bic with strict=False.
    Useful when you only need a boolean result without error details.

    Args:
        bic: BIC/SWIFT code to validate.
        field: Optional field name (unused, for API compatibility).

    Returns:
        True if BIC is valid, False otherwise.

    Example:
        >>> if validate_bic_safe("DEUTDEFF"):
        ...     print("Valid BIC")
    """
    is_valid, _ = validate_bic(bic, field=field, strict=False)
    return is_valid
