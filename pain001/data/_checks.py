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

"""Checks every payment loader shares: line numbers, refusals, identifiers.

Split from :mod:`pain001.data.loader` so the whole-input and streaming
loaders (:mod:`pain001.data._streaming`) share them.
"""

import os
from collections.abc import Sequence
from typing import Any

from pain001.exceptions import PaymentValidationError, RowIssue, format_issues

#: Line of the first row in a file with a header line; a row counts
#: from 1 in every other input.
_HEADER_FIRST_LINE = {".csv": 2}


def _first_line(data_source: object) -> int:
    """Return the line of the first row of ``data_source``, from 1.

    Args:
        data_source: A file path, a list of rows or one row.

    Returns:
        2 for a CSV file (its header is line 1), else 1.
    """
    if not isinstance(data_source, str):
        return 1
    ext = os.path.splitext(data_source)[1].lower()
    return _HEADER_FIRST_LINE.get(ext, 1)


def _refuse(headline: str, issues: Sequence[RowIssue]) -> None:
    """Raise a PaymentValidationError listing ``issues``, if any.

    Args:
        headline: The message's first line.
        issues: The problems found; nothing is raised when empty.

    Raises:
        PaymentValidationError: Carrying ``issues`` on ``errors`` and
            listing the first of them in its message.
    """
    if issues:
        count = f"{len(issues)} problem{'s' if len(issues) > 1 else ''}"
        raise PaymentValidationError(
            f"{headline} ({count}):{format_issues(issues)}",
            field=issues[0].column,
            errors=issues,
        )


def _checked(
    rows: list[dict[str, Any]],
    identifier_checks: bool,
    start: int = 0,
    first_line: int = 1,
) -> list[dict[str, Any]]:
    """Return ``rows`` once their IBAN and BIC columns pass, if asked.

    Args:
        rows: Loaded payment rows (a whole input, or one chunk of it).
        identifier_checks: False returns ``rows`` unchecked.
        start: Index of the first row, so a chunk's errors name the
            row of the whole input.
        first_line: The line of the input's first row (2 for CSV).

    Returns:
        ``rows``, unchanged.
    """
    if identifier_checks:
        # Imported here: pain001.validation imports this module.
        from pain001.validation._identifiers import check_identifiers

        check_identifiers(rows, start, first_line)
    return rows
