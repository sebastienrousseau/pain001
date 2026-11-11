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

"""Pure diagnostic engine for Pain001 payment CSV documents.

This module has no LSP or editor dependencies, so it can be unit-tested in
isolation and reused anywhere (the CLI, CI linters, the LSP server). Given
the raw text of a CSV file it returns a list of :class:`Diagnostic` objects
locating problems that would make the file fail ISO 20022 generation —
missing required columns and malformed IBAN/BIC/LEI/currency cells — by reusing
the same validators the generator uses.
"""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from pain001.constants import valid_xml_types
from pain001.schemas.required_columns import required_columns
from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.charset import find_invalid_characters
from pain001.validation.iban_validator import validate_iban_safe
from pain001.validation.lei_validator import lei_error


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


def _required_columns(message_type: str) -> frozenset[str]:
    """Return the required column set for a message type.

    The set is the ``required`` list of the bundled JSON schema, the
    same contract the CSV and SQLite validators enforce. A message type
    that is not bundled falls back to the columns every bundled schema
    describes.

    Args:
        message_type: ISO 20022 message type (e.g. ``pain.001.001.03``).

    Returns:
        The set of column names that must be present.
    """
    if message_type not in valid_xml_types:
        return frozenset(required_columns())
    return frozenset(required_columns(message_type))


def _cell_spans(line_text: str) -> list[tuple[int, int]]:
    """Compute the character span of every CSV cell on a line, in one pass.

    A best-effort locator that splits on commas, which is sufficient for the
    simple, unquoted payment CSVs Pain001 consumes.

    This used to be a per-cell function that split the line and then summed
    the lengths of every preceding cell to find the offset. Both halves of
    that were repeated for each cell, making span computation quadratic in
    the column count: a 20-column row did ~200 length operations instead of
    ~20, and the generator inside the ``sum`` ran 525,000 times for a
    500-row document. Accumulating the offset across a single walk gives
    identical spans for linear work.

    Args:
        line_text: The raw text of the CSV line.

    Returns:
        One ``(start, end)`` character range per cell, in column order.
    """
    spans: list[tuple[int, int]] = []
    offset = 0
    for part in line_text.split(","):
        spans.append((offset, offset + len(part)))
        offset += len(part) + 1  # +1 for the comma
    return spans


def _span_for(
    spans: list[tuple[int, int]], column_index: int, line_len: int
) -> tuple[int, int]:
    """Return the span for ``column_index``, falling back to the whole line.

    Args:
        spans: Precomputed spans for the line, from :func:`_cell_spans`.
        column_index: Zero-based index of the target cell.
        line_len: Length of the line, used for the out-of-range fallback.

    Returns:
        A ``(start, end)`` character range for the cell.
    """
    if column_index >= len(spans):  # pragma: no cover - defensive
        return 0, line_len
    return spans[column_index]


def _iban_problem(value: str) -> str | None:
    """Return the IBAN diagnostic message, or ``None`` when valid."""
    return None if validate_iban_safe(value) else f"Invalid IBAN: {value!r}"


def _bic_problem(value: str) -> str | None:
    """Return the BIC diagnostic message, or ``None`` when valid."""
    return None if validate_bic_safe(value) else f"Invalid BIC: {value!r}"


def _lei_problem(value: str) -> str | None:
    """Return the LEI diagnostic message, or ``None`` when valid."""
    reason = lei_error(value)
    return None if reason is None else f"Invalid LEI: {value!r} ({reason})"


def _currency_problem(value: str) -> str | None:
    """Return the currency diagnostic message, or ``None`` when valid."""
    if value.isalpha() and len(value) == 3:
        return None
    return f"Invalid ISO 4217 currency code: {value!r}"


#: Column kind to (cell check, diagnostic code).
_CELL_CHECKS: dict[str, tuple[Callable[[str], str | None], str]] = {
    "iban": (_iban_problem, "invalid-iban"),
    "bic": (_bic_problem, "invalid-bic"),
    "lei": (_lei_problem, "invalid-lei"),
    "currency": (_currency_problem, "invalid-currency"),
}


def _column_kind(name: str) -> str | None:
    """Classify a header cell by name convention.

    Args:
        name: The stripped header cell.

    Returns:
        ``iban``, ``bic``, ``lei`` or ``currency``, else ``None``.
    """
    upper = name.upper()
    if upper.endswith("IBAN"):
        return "iban"
    if upper.endswith("BIC"):
        return "bic"
    if upper == "LEI" or upper.endswith("_LEI"):
        return "lei"
    return "currency" if upper in ("CURRENCY", "PAYMENT_CURRENCY") else None


def _missing_column_diagnostics(
    header: list[str], header_line: str, message_type: str
) -> list[Diagnostic]:
    """Report each absent required column on the header line."""
    missing = sorted(_required_columns(message_type) - set(header))
    return [
        Diagnostic(
            line=0,
            col_start=0,
            col_end=len(header_line),
            severity=Severity.ERROR,
            message=f"Missing required column: {name!r}",
            code="missing-column",
        )
        for name in missing
    ]


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

    rows = list(csv.reader(io.StringIO(text)))
    header = [cell.strip() for cell in rows[0]]
    diagnostics = _missing_column_diagnostics(header, lines[0], message_type)
    kinds = {
        index: kind
        for index, name in enumerate(header)
        if (kind := _column_kind(name)) is not None
    }
    for row_index, row in enumerate(rows[1:], start=1):
        if any(cell.strip() for cell in row):
            diagnostics.extend(_row_diagnostics(row_index, row, lines, kinds))
    return diagnostics


def _row_diagnostics(
    row_index: int, row: list[str], lines: list[str], kinds: dict[int, str]
) -> list[Diagnostic]:
    """Validate every non-empty cell of one data row.

    Args:
        row_index: Zero-based line index of the row.
        row: The parsed cells.
        lines: Every line of the document.
        kinds: Column index to column kind, from :func:`_column_kind`.

    Returns:
        One diagnostic per malformed cell.
    """
    if row_index < len(lines):
        line_text = lines[row_index]
    else:  # pragma: no cover - rows never exceed text lines
        line_text = ""
    # Once per row, not once per cell: this is the whole fix.
    spans = _cell_spans(line_text)
    found: list[Diagnostic] = []
    for col, raw in enumerate(row):
        value = raw.strip()
        if not value:
            continue
        start, end = _span_for(spans, col, len(line_text))
        diag = _validate_cell(row_index, start, end, value, kinds.get(col))
        if diag is not None:
            found.append(diag)
    return found


def _validate_cell(
    line: int, start: int, end: int, value: str, kind: str | None
) -> Diagnostic | None:
    """Validate a single cell and return a diagnostic if it is malformed.

    Args:
        line: Zero-based line index of the cell.
        start: Zero-based start character of the cell.
        end: Zero-based end character (exclusive) of the cell.
        value: The (stripped, non-empty) cell value.
        kind: The column's kind (``iban``, ``bic``, ``lei``,
            ``currency``), or ``None`` for any other column.

    Returns:
        A :class:`Diagnostic` describing the problem, or ``None`` if valid.
    """
    if kind is not None:
        check, code = _CELL_CHECKS[kind]
        message = check(value)
        if message is not None:
            return Diagnostic(line, start, end, Severity.ERROR, message, code)
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
