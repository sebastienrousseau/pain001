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

"""Account identifier checks every load runs, scheme or no scheme.

Until 0.0.81 an IBAN with a broken mod-97 check digit, or a BIC that is
not ISO 9362, passed every check but a scheme profile's: the XSD
patterns only test the character classes, so the file was written and
the bank rejected it. The loaders now run these checks on every row
unless the caller opts out (``identifier_checks=False``, or the CLI's
``--no-identifier-checks``).

The checked columns are the ones the bundled templates render into an
``IBAN``, ``BIC`` or ``BICFI`` element, in any spelling the generator
accepts (``debtor_account_iban`` is ``debtor_account_IBAN``). An empty
value is left to the required-field checks: a version 09 row may name
an account by number instead of IBAN.

Messages name the line (counted from 1 as a spreadsheet shows it, so a
CSV file's first payment is line 2) and the column, and never repeat
the identifier: an IBAN is personal data. The error carries one
:class:`~pain001.exceptions.RowIssue` per finding on ``errors``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pain001.exceptions import (
    MAX_LISTED_ISSUES,
    IssueCode,
    PaymentValidationError,
    RowIssue,
    format_issues,
)
from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.iban_validator import validate_iban

#: Column, in its canonical spelling, to the identifier it carries.
#: ``creditor_agent_BICFI`` is the fallback the 05-08 builders read when
#: ``creditor_agent_BIC`` is absent.
IDENTIFIER_COLUMNS: dict[str, str] = {
    "debtor_account_IBAN": "IBAN",
    "creditor_account_IBAN": "IBAN",
    "debtor_agent_BIC": "BIC",
    "creditor_agent_BIC": "BIC",
    "creditor_agent_BICFI": "BIC",
}
_BY_LOWER = {column.lower(): column for column in IDENTIFIER_COLUMNS}

_BIC_REASON = (
    "not a valid BIC (ISO 9362: 8 or 11 characters, a 4-letter bank "
    "code and a known 2-letter country code)"
)

#: At most this many findings are listed in one error message.
MAX_LISTED = MAX_LISTED_ISSUES

#: Issue code per identifier kind.
_CODES = {"IBAN": IssueCode.INVALID_IBAN, "BIC": IssueCode.INVALID_BIC}


def _reason(kind: str, value: str) -> str | None:
    """Return why ``value`` is not a valid ``kind``, or ``None``.

    Args:
        kind: ``"IBAN"`` or ``"BIC"``.
        value: The stripped, non-empty column value.

    Returns:
        The reason, free of the value itself, or ``None`` when valid.
    """
    if kind == "BIC":
        return None if validate_bic_safe(value) else _BIC_REASON
    is_valid, error = validate_iban(value, strict=False)
    return None if is_valid else f"not a valid IBAN ({error})"


def row_errors(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Return ``(column, reason)`` for each invalid identifier in ``row``.

    Args:
        row: One payment row.

    Returns:
        The findings in the row's column order; empty when it is clean.
    """
    found: list[tuple[str, str]] = []
    for key, raw in row.items():
        column = _BY_LOWER.get(str(key).lower())
        value = "" if raw is None else str(raw).strip()
        if column is None or not value:
            continue
        reason = _reason(IDENTIFIER_COLUMNS[column], value)
        if reason is not None:
            found.append((str(key), reason))
    return found


def identifier_errors(
    rows: Iterable[Mapping[str, Any]], start: int = 0
) -> list[tuple[int, str, str]]:
    """Return ``(row index, column, reason)`` per invalid identifier.

    Args:
        rows: The payment rows.
        start: Index of the first row, for a chunk of a larger input.

    Returns:
        The findings in row order; empty when every identifier is valid.
    """
    return [
        (index, column, reason)
        for index, row in enumerate(rows, start=start)
        for column, reason in row_errors(row)
    ]


def check_identifiers(
    rows: Iterable[Mapping[str, Any]], start: int = 0, first_line: int = 1
) -> None:
    """Raise when any row carries an invalid IBAN or BIC.

    Args:
        rows: The payment rows.
        start: Index of the first row, for a chunk of a larger input.
        first_line: The line of the input's first row: 2 for a CSV
            file, whose header is line 1, else 1.

    Raises:
        PaymentValidationError: Listing the line and column of each
            finding (the first twenty), never the value, with one
            :class:`~pain001.exceptions.RowIssue` each on ``errors``.
    """
    errors = identifier_errors(rows, start)
    if not errors:
        return
    issues = [
        RowIssue(
            first_line + index,
            column,
            _CODES[IDENTIFIER_COLUMNS[_BY_LOWER[column.lower()]]],
            reason,
        )
        for index, column, reason in errors
    ]
    raise PaymentValidationError(
        f"Invalid account identifiers ({len(errors)}):"
        f"{format_issues(issues)}\n"
        "Fix the values, or skip these checks with --no-identifier-checks "
        "(identifier_checks=False).",
        field=errors[0][1],
        errors=issues,
    )
