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

"""Pure diagnostic engine for Pain001 payment CSV documents.

This module has no LSP or editor dependencies, so it can be unit-tested in
isolation and reused anywhere (the CLI, CI linters, the LSP server). Given
the raw text of a CSV file it returns a list of :class:`Diagnostic` objects
locating problems that would make the file fail ISO 20022 generation —
missing required columns and malformed IBAN/BIC/currency cells — by reusing
the same validators the generator uses.
"""

import csv
import io
from dataclasses import dataclass
from enum import IntEnum

from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.charset import find_invalid_characters
from pain001.validation.iban_validator import validate_iban_safe


class Severity(IntEnum):
    """Diagnostic severity, matching the LSP numeric scale."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass(frozen=True)
class Diagnostic:
    """A single editor diagnostic over a 0-based line/character range.

    Attributes:
        line: Zero-based line index of the affected text.
        col_start: Zero-based start character on the line.
        col_end: Zero-based end character (exclusive) on the line.
        severity: Diagnostic severity.
        message: Human-readable description of the problem.
        code: Stable machine-readable rule identifier.
    """

    line: int
    col_start: int
    col_end: int
    severity: Severity
    message: str
    code: str


# Core columns each family of message must provide. Kept deliberately
# minimal — the optional remainder is validated only when present.
_CREDIT_TRANSFER_REQUIRED = frozenset(
    {
        "id",
        "payment_amount",
        "currency",
        "debtor_name",
        "debtor_account_IBAN",
        "creditor_name",
        "creditor_account_IBAN",
    }
)
_DIRECT_DEBIT_REQUIRED = _CREDIT_TRANSFER_REQUIRED | {
    "mandate_id",
    "sequence_type",
}


def _required_columns(message_type: str) -> frozenset[str]:
    """Return the required column set for a message type.

    Args:
        message_type: ISO 20022 message type (e.g. ``pain.001.001.03``).

    Returns:
        The set of column names that must be present.
    """
    if message_type.startswith("pain.008"):
        return _DIRECT_DEBIT_REQUIRED
    return _CREDIT_TRANSFER_REQUIRED


def _cell_span(line_text: str, column_index: int) -> tuple[int, int]:
    """Compute the character span of a CSV cell on a line.

    A best-effort locator that splits on commas (sufficient for the simple,
    unquoted payment CSVs Pain001 consumes); it falls back to the whole line
    when the column index is out of range.

    Args:
        line_text: The raw text of the CSV line.
        column_index: Zero-based index of the target cell.

    Returns:
        A ``(start, end)`` character range for the cell.
    """
    parts = line_text.split(",")
    if column_index >= len(parts):  # pragma: no cover - defensive
        return 0, len(line_text)
    start = sum(len(p) + 1 for p in parts[:column_index])
    return start, start + len(parts[column_index])


def diagnostics_for_csv(
    text: str, message_type: str = "pain.001.001.03"
) -> list[Diagnostic]:
    """Lint a payment CSV document and return diagnostics.

    Args:
        text: The full text of the CSV document.
        message_type: ISO 20022 message type the file targets.

    Returns:
        A list of :class:`Diagnostic` objects (empty when the file is clean
        or has no header row).
    """
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        return []

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    header = [cell.strip() for cell in rows[0]]
    diagnostics: list[Diagnostic] = []

    # 1. Missing required columns (reported on the header line).
    present = set(header)
    missing = sorted(_required_columns(message_type) - present)
    for name in missing:
        diagnostics.append(
            Diagnostic(
                line=0,
                col_start=0,
                col_end=len(lines[0]),
                severity=Severity.ERROR,
                message=f"Missing required column: {name!r}",
                code="missing-column",
            )
        )

    # Column classification by name convention.
    iban_cols = {
        i for i, name in enumerate(header) if name.upper().endswith("IBAN")
    }
    bic_cols = {
        i for i, name in enumerate(header) if name.upper().endswith("BIC")
    }
    currency_cols = {
        i
        for i, name in enumerate(header)
        if name.lower() in ("currency", "payment_currency")
    }

    # 2. Per-cell validation for each data row.
    for row_index, row in enumerate(rows[1:], start=1):
        if not any(cell.strip() for cell in row):
            continue
        if row_index < len(lines):
            line_text = lines[row_index]
        else:  # pragma: no cover - rows never exceed text lines
            line_text = ""
        for col, value in enumerate(row):
            value = value.strip()
            if not value:
                continue
            diag = _validate_cell(
                row_index,
                col,
                value,
                line_text,
                iban_cols,
                bic_cols,
                currency_cols,
            )
            if diag is not None:
                diagnostics.append(diag)
    return diagnostics


def _validate_cell(
    line: int,
    col: int,
    value: str,
    line_text: str,
    iban_cols: set[int],
    bic_cols: set[int],
    currency_cols: set[int],
) -> Diagnostic | None:
    """Validate a single cell and return a diagnostic if it is malformed.

    Args:
        line: Zero-based line index of the cell.
        col: Zero-based column index of the cell.
        value: The (stripped, non-empty) cell value.
        line_text: Raw text of the line, for span computation.
        iban_cols: Column indices holding IBANs.
        bic_cols: Column indices holding BICs.
        currency_cols: Column indices holding currency codes.

    Returns:
        A :class:`Diagnostic` describing the problem, or ``None`` if valid.
    """
    start, end = _cell_span(line_text, col)
    if col in iban_cols and not validate_iban_safe(value):
        return Diagnostic(
            line,
            start,
            end,
            Severity.ERROR,
            f"Invalid IBAN: {value!r}",
            "invalid-iban",
        )
    if col in bic_cols and not validate_bic_safe(value):
        return Diagnostic(
            line,
            start,
            end,
            Severity.ERROR,
            f"Invalid BIC: {value!r}",
            "invalid-bic",
        )
    if col in currency_cols and not (value.isalpha() and len(value) == 3):
        return Diagnostic(
            line,
            start,
            end,
            Severity.ERROR,
            f"Invalid ISO 4217 currency code: {value!r}",
            "invalid-currency",
        )
    invalid_chars = find_invalid_characters(value)
    if invalid_chars:
        return Diagnostic(
            line,
            start,
            end,
            Severity.WARNING,
            "Characters outside the ISO 20022 Latin set: "
            f"{', '.join(invalid_chars)}",
            "invalid-charset",
        )
    return None
