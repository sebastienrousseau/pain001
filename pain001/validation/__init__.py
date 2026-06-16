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

"""Validation module for Pain001.

This module provides centralized validation services for payment data,
templates, schemas, and data sources.
"""

from pain001.validation.bic_validator import (
    validate_bic,
    validate_bic_format,
    validate_bic_safe,
)
from pain001.validation.charset import (
    ISO20022_ALLOWED_CHARACTERS,
    find_invalid_characters,
    is_valid_charset,
    sanitize_to_charset,
)
from pain001.validation.iban_validator import (
    validate_iban,
    validate_iban_checksum,
    validate_iban_format,
    validate_iban_safe,
)
from pain001.validation.schemes import (
    PROFILES,
    SchemeValidationResult,
    SchemeViolation,
    SepaCreditTransferProfile,
    ValidationProfile,
    validate_scheme,
)
from pain001.validation.service import (
    ValidationConfig,
    ValidationReport,
    ValidationResult,
    ValidationService,
)

__all__ = [
    # Service classes
    "ValidationService",
    "ValidationConfig",
    "ValidationResult",
    "ValidationReport",
    # IBAN validation
    "validate_iban",
    "validate_iban_format",
    "validate_iban_checksum",
    "validate_iban_safe",
    # BIC validation
    "validate_bic",
    "validate_bic_format",
    "validate_bic_safe",
    # ISO 20022 character set
    "ISO20022_ALLOWED_CHARACTERS",
    "find_invalid_characters",
    "is_valid_charset",
    "sanitize_to_charset",
    # Scheme rulebook validation
    "validate_scheme",
    "ValidationProfile",
    "SepaCreditTransferProfile",
    "SchemeValidationResult",
    "SchemeViolation",
    "PROFILES",
]
