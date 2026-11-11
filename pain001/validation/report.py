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

"""The results every validation surface reports.

:class:`ValidationResult` is one check's outcome; :class:`ValidationReport`
gathers them, and is what :func:`pain001.validate` and
:meth:`pain001.validation.ValidationService.validate_all` return.
"""

from dataclasses import dataclass, field

from pain001.exceptions import RowIssue
from pain001.validation._scheme_types import SchemeViolation

__all__ = ["ValidationReport", "ValidationResult"]


@dataclass
class ValidationResult:
    """Result of a single validation check.

    Attributes:
        is_valid: Whether the validation passed.
        error: Optional error message if validation failed.
        field: Optional field name that caused the validation error.
        details: Optional additional details about the validation.
    """

    is_valid: bool
    error: str | None = None
    field: str | None = None
    details: str | None = None


@dataclass
class ValidationReport:
    """Comprehensive validation report for all checks.

    :func:`pain001.validate` fills the row counts and findings;
    :meth:`~pain001.validation.ValidationService.validate_all` leaves
    them empty.

    Attributes:
        is_valid: Whether all validations passed.
        errors: List of error messages from failed validations.
        results: Dictionary of individual validation results.
        total_rows: Rows loaded (0 when the input was refused before
            its rows could be counted: a missing column, a bad IBAN).
        valid_rows: Rows with no JSON Schema finding.
        issues: Every row finding, without the values.
        scheme_violations: The scheme rung's findings, warnings
            included, when a scheme or policy was asked for.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    results: dict[str, ValidationResult] = field(default_factory=dict)
    total_rows: int = 0
    valid_rows: int = 0
    issues: list[RowIssue] = field(default_factory=list)
    scheme_violations: list[SchemeViolation] = field(default_factory=list)

    @property
    def invalid_rows(self) -> int:
        """Return the number of rows with at least one schema finding."""
        return self.total_rows - self.valid_rows

    def record(
        self, name: str, result: ValidationResult, fallback: str
    ) -> None:
        """Store one check's result, failing the report if it failed.

        Args:
            name: The check's key in :attr:`results`.
            result: The check's result.
            fallback: Error message to use when the result carries none.
        """
        self.results[name] = result
        if not result.is_valid:
            self.is_valid = False
            self.errors.append(result.error or fallback)
