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

"""The one validation ladder the CLI, Python and REST surfaces run.

A payment file climbs four rungs, in this order:

1. **Row contract**: the loader's checks (required columns, numbers,
   amounts, booleans, dates) and the one-batch check.
2. **Identifiers**: IBAN, BIC and LEI check digits, unless switched
   off (both run inside :func:`pain001.validation._one_batch.load_batch`).
3. **JSON Schema**: every row against the message type's bundled
   schema (``pain001/schemas``) and any registered validator plugin.
4. **Scheme**: an optional rulebook or private policy.

Rungs 1 and 2 refuse the whole input with a ``PaymentValidationError``
(there is no row to count once a column is missing). Rungs 3 and 4
report per row, so a caller can show counts; :meth:`Ladder.require_valid`
turns rung 3's findings into the same exception for callers that
generate. Before 0.0.87 the CLI and :func:`pain001.core.core.process_files`
skipped rung 3 and accepted ``currency=EURO``, which the REST API
refused.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pain001.data._checks import _first_line
from pain001.data.loader import load_payment_data_streaming
from pain001.exceptions import (
    IssueCode,
    PaymentValidationError,
    RowIssue,
    format_issues,
)
from pain001.validation._one_batch import load_batch
from pain001.validation.schema_validator import SchemaValidator
from pain001.validation.schema_validator import (
    ValidationError as SchemaError,
)
from pain001.validation.schemes import SchemeValidationResult, validate_scheme

__all__ = [
    "Ladder",
    "check_scheme",
    "load_valid",
    "load_valid_chunks",
    "read_policy",
    "require_schema_valid",
    "run_ladder",
    "schema_issues",
]

RowErrors = list[tuple[int, list[SchemaError]]]
"""Schema findings: ``(row index, errors)`` for each failing row."""


def _issue(error: SchemaError, line: int) -> RowIssue:
    """Turn one schema finding into a :class:`RowIssue` without its value.

    Args:
        error: The finding.
        line: The row's line, counted from 1.

    Returns:
        The issue; a string value quoted in the message is replaced by
        "the value", since a row issue never carries the value.
    """
    message = error.message
    if isinstance(error.value, str) and error.value:
        message = message.replace(repr(error.value), "the value")
    column = error.path[2:] if error.path.startswith("$.") else None
    return RowIssue(line, column, IssueCode.SCHEMA_VIOLATION, message)


def schema_issues(
    errors: RowErrors, start: int = 0, first_line: int = 1
) -> list[RowIssue]:
    """Return one :class:`RowIssue` per schema finding, in row order.

    Args:
        errors: The findings, as ``SchemaValidator.validate_batch``
            returns them.
        start: Index of the first row in the whole input (for chunks).
        first_line: The line of the input's first row.

    Returns:
        The issues.
    """
    base = first_line + start
    return [
        _issue(error, base + index)
        for index, row_errors in errors
        for error in row_errors
    ]


def require_schema_valid(
    rows: list[dict[str, Any]],
    message_type: str,
    start: int = 0,
    first_line: int = 1,
) -> None:
    """Refuse ``rows`` unless every one passes the JSON Schema rung.

    Args:
        rows: Loaded rows (a whole input, or one chunk of it).
        message_type: The target message type.
        start: Index of the first row in the whole input.
        first_line: The line of the input's first row.

    A ``PaymentValidationError`` listing each finding as a ``RowIssue``
    with code ``P001-E030`` is raised when any row fails.
    """
    _, _, errors = SchemaValidator(message_type).validate_batch(rows)
    _refuse(message_type, schema_issues(errors, start, first_line))


def _refuse(message_type: str, issues: Sequence[RowIssue]) -> None:
    """Raise a ``PaymentValidationError`` for ``issues``, if there are any.

    Args:
        message_type: The schema's message type, for the headline.
        issues: The problems found.

    Raises:
        PaymentValidationError: When ``issues`` is not empty.
    """
    if issues:
        count = f"{len(issues)} problem{'s' if len(issues) > 1 else ''}"
        raise PaymentValidationError(
            f"{message_type} schema validation failed ({count}):"
            f"{format_issues(issues)}",
            field=issues[0].column,
            errors=issues,
        )


def read_policy(path: str | Path) -> str:
    """Read a private policy file, at most one byte past the size cap.

    The policy parser refuses anything longer, so a huge file is never
    read whole.

    Args:
        path: The YAML policy file.

    Returns:
        The policy source.

    Raises:
        ValueError: If the ``rules`` extra is not installed.
    """
    try:
        from pain001.validation.policy import MAX_POLICY_BYTES
    except ImportError as exc:
        raise ValueError("Custom rules require 'pain001[rules]'.") from exc
    with Path(path).open(encoding="utf-8") as handle:
        return handle.read(MAX_POLICY_BYTES + 1)


def check_scheme(
    rows: list[dict[str, Any]],
    message_type: str,
    scheme: str | None = None,
    rules: str | None = None,
) -> SchemeValidationResult:
    """Run the scheme rung: a rulebook, a private policy, or both.

    Args:
        rows: Loaded rows.
        message_type: The target message type.
        scheme: A scheme profile name (``sepa-sct``), if any.
        rules: A private YAML policy's source text, if any.

    Returns:
        The findings.

    Raises:
        ValueError: For an unknown scheme, a bad policy, or a policy
            without the ``rules`` extra installed.
    """
    if rules is not None:
        try:
            from pain001.validation.policy import validate_policy
        except ImportError as exc:
            raise ValueError("Custom rules require 'pain001[rules]'.") from exc
        return validate_policy(rows, rules, scheme, message_type)
    return validate_scheme(rows, scheme or "", message_type=message_type)


@dataclass(frozen=True)
class Ladder:
    """What the ladder found for one input.

    Attributes:
        rows: The loaded rows.
        message_type: The target message type.
        row_errors: Schema findings, ``(row index, errors)`` per row.
        first_line: The line of the first row (2 for CSV, else 1).
        scheme: The scheme rung's findings, when one was asked for.
    """

    rows: list[dict[str, Any]]
    message_type: str
    row_errors: RowErrors
    first_line: int = 1
    scheme: SchemeValidationResult | None = None

    @property
    def total(self) -> int:
        """Return the number of rows loaded."""
        return len(self.rows)

    @property
    def invalid(self) -> int:
        """Return the number of rows with at least one schema finding."""
        return len(self.row_errors)

    @property
    def valid(self) -> int:
        """Return the number of rows with no schema finding."""
        return self.total - self.invalid

    @property
    def is_valid(self) -> bool:
        """Return True when no row and no scheme rule failed."""
        scheme_ok = self.scheme is None or self.scheme.is_valid
        return not self.row_errors and scheme_ok

    def issues(self) -> list[RowIssue]:
        """Return the schema findings as row issues, in row order."""
        return schema_issues(self.row_errors, first_line=self.first_line)

    def require_valid(self) -> Ladder:
        """Refuse the input if any row failed the JSON Schema rung.

        A ``PaymentValidationError`` listing each finding is raised
        when any row failed.

        Returns:
            This result, for chaining.
        """
        _refuse(self.message_type, self.issues())
        return self


def run_ladder(
    source: str | Path | list[dict[str, Any]] | dict[str, Any],
    message_type: str,
    *,
    identifier_checks: bool = True,
    scheme: str | None = None,
    rules: str | None = None,
    after_load: Callable[[], None] | None = None,
) -> Ladder:
    """Climb the ladder for one input.

    Args:
        source: A data file path, a list of rows or one row.
        message_type: The target message type.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.
        scheme: A scheme profile to check rows against, if any.
        rules: A private YAML policy's source text, if any.
        after_load: Called once rungs 1 and 2 pass, before the JSON
            Schema rung (a job reports its progress, and sees a cancel,
            there).

    Returns:
        The rows and every per-row finding.

    A ``PaymentValidationError`` from rungs 1 and 2, and a
    ``ValueError`` from :func:`check_scheme`, propagate unchanged.
    """
    if isinstance(source, Path):
        source = str(source)
    rows = load_batch(source, message_type, identifier_checks)
    if after_load is not None:
        after_load()
    _, _, errors = SchemaValidator(message_type).validate_batch(rows)
    result = None
    if scheme or rules is not None:
        result = check_scheme(rows, message_type, scheme, rules)
    return Ladder(rows, message_type, errors, _first_line(source), result)


def load_valid(
    source: str | Path | list[dict[str, Any]] | dict[str, Any],
    message_type: str,
    identifier_checks: bool = True,
) -> list[dict[str, Any]]:
    """Return the rows of ``source`` once they pass rungs 1 to 3.

    Args:
        source: A data file path, a list of rows or one row.
        message_type: The target message type.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.

    Returns:
        The loaded rows.

    A ``PaymentValidationError`` from any rung propagates unchanged.
    """
    ladder = run_ladder(
        source, message_type, identifier_checks=identifier_checks
    )
    return ladder.require_valid().rows


def load_valid_chunks(
    data_file_path: str,
    message_type: str,
    chunk_size: int,
    identifier_checks: bool = True,
) -> Iterator[list[dict[str, Any]]]:
    """Yield the chunks of a file, each once it passes rungs 1 to 3.

    Each chunk is its own file once generated, so the one-batch check
    applies per chunk at generation, not here.

    Args:
        data_file_path: The data file.
        message_type: The target message type.
        chunk_size: Rows per chunk.
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.

    Yields:
        list[dict[str, Any]]: Each chunk's rows.

    A ``PaymentValidationError`` naming lines of the whole input
    propagates from the first chunk that fails; earlier chunks have
    already been yielded.
    """
    first_line = _first_line(data_file_path)
    start = 0
    for chunk in load_payment_data_streaming(
        data_file_path,
        chunk_size,
        identifier_checks=identifier_checks,
        message_type=message_type,
    ):
        require_schema_valid(chunk, message_type, start, first_line)
        start += len(chunk)
        yield chunk
