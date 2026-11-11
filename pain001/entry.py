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

"""``pain001.generate`` and ``pain001.validate``: no template paths.

The two calls a program needs, with the bundled template and schema of
the message type. Both run the ladder ``pain001 validate`` and the
REST API run (:mod:`pain001.validation.ladder`), so the three surfaces
give one verdict for one input.

Example:
    >>> import pain001
    >>> report = pain001.validate("payments.csv", "pain.001.001.03")
    >>> if report.is_valid:
    ...     result = pain001.generate("payments.csv", "pain.001.001.03")
    ...     print(result.path)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pain001.exceptions import (
    IssueCode,
    PaymentValidationError,
    RowIssue,
    format_issues,
)
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation.ladder import Ladder, run_ladder
from pain001.validation.report import ValidationReport
from pain001.validation.schemes import SchemeViolation

__all__ = ["GenerationResult", "generate", "validate"]

DEFAULT_MESSAGE_TYPE = "pain.001.001.03"
"""The message type used when a call names none."""

Source = str | Path | list[dict[str, Any]] | dict[str, Any]
"""A data file path, a list of payment rows, or one payment row."""


@dataclass(frozen=True)
class GenerationResult:
    """What :func:`generate` wrote.

    Attributes:
        path: The XML file written.
        message_type: The message type generated.
        rows: The number of payment rows in it.
    """

    path: Path
    message_type: str
    rows: int


def _scheme_issues(ladder: Ladder) -> list[RowIssue]:
    """Return the scheme rung's errors as row issues (warnings dropped).

    Args:
        ladder: The ladder's result.

    Returns:
        One issue per scheme error, coded ``P001-E040``.
    """
    violations: list[SchemeViolation] = (
        list(ladder.scheme.violations) if ladder.scheme is not None else []
    )
    return [
        RowIssue(
            ladder.first_line + v.index,
            v.field,
            IssueCode.SCHEME_VIOLATION,
            # The violation's message can quote an IBAN; an issue never
            # carries a value, so it names the rule only.
            f"breaks scheme rule {v.rule}",
        )
        for v in violations
        if v.severity == "error"
    ]


def validate(
    data: Source,
    message_type: str = DEFAULT_MESSAGE_TYPE,
    *,
    scheme: str | None = None,
    rules: str | None = None,
    identifier_checks: bool = True,
) -> ValidationReport:
    """Validate payment data the way ``pain001 validate`` does.

    Args:
        data: A data file path (under the working or temporary
            directory), a list of payment rows, or one row.
        message_type: The target message type.
        scheme: A scheme profile to check rows against (``sepa-sct``).
        rules: A private YAML policy's source text (``pain001[rules]``).
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.

    Returns:
        The report. A refused input is ``is_valid=False`` with its
        issues; ``total_rows`` stays 0 when the loader refused it.

    A ``ValueError`` (an unknown message type or scheme, a bad policy)
    and a ``FileNotFoundError`` (no such data file) propagate.
    """
    try:
        ladder = run_ladder(
            data,
            message_type,
            identifier_checks=identifier_checks,
            scheme=scheme,
            rules=rules,
        )
    except PaymentValidationError as exc:
        return ValidationReport(
            is_valid=False, errors=[str(exc)], issues=list(exc.errors)
        )
    issues = ladder.issues() + _scheme_issues(ladder)
    return ValidationReport(
        is_valid=ladder.is_valid,
        errors=[str(issue) for issue in issues],
        total_rows=ladder.total,
        valid_rows=ladder.valid,
        issues=issues,
        scheme_violations=list(ladder.scheme.violations)
        if ladder.scheme is not None
        else [],
    )


def generate(
    data: Source,
    message_type: str = DEFAULT_MESSAGE_TYPE,
    *,
    output_dir: str | Path | None = None,
    scheme: str | None = None,
    rules: str | None = None,
    identifier_checks: bool = True,
) -> GenerationResult:
    """Validate payment data, then write it as XML with the bundled template.

    Args:
        data: A data file path (under the working or temporary
            directory), a list of payment rows, or one row.
        message_type: The message type to generate.
        output_dir: The directory to write ``<message_type>.xml`` in,
            created if missing; the working directory when omitted.
        scheme: A scheme profile the rows must pass (``sepa-sct``).
        rules: A private YAML policy's source text (``pain001[rules]``).
        identifier_checks: If False, skip the IBAN, BIC and LEI checks.

    Returns:
        Where the file was written and how many rows it holds.

    Raises:
        PaymentValidationError: If any rung of the ladder refused the
            data; ``errors`` lists each problem as a ``RowIssue``.

    A ``ValueError`` for an unknown message type or scheme propagates.
    """
    ladder = run_ladder(
        data,
        message_type,
        identifier_checks=identifier_checks,
        scheme=scheme,
        rules=rules,
    ).require_valid()
    refused = _scheme_issues(ladder)
    if refused:
        raise PaymentValidationError(
            f"Scheme validation failed:{format_issues(refused)}",
            field=refused[0].column,
            errors=refused,
        )
    # Imported here: the XML stack is the slow part of ``import pain001``.
    from pain001.xml.generate_xml import generate_xml

    template, schema = DEFAULT_TEMPLATE_REGISTRY.resolve_paths(message_type)
    directory = Path(output_dir) if output_dir is not None else Path.cwd()
    directory.mkdir(parents=True, exist_ok=True)
    written = generate_xml(
        ladder.rows,
        message_type,
        template,
        schema,
        output_path=str(directory / f"{message_type}.xml"),
    )
    return GenerationResult(Path(written), message_type, ladder.total)
