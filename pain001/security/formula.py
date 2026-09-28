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

"""Formula injection mitigation for CSV and spreadsheet inputs."""

from __future__ import annotations

#: Characters that spreadsheet engines interpret as formula prefixes.
FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r", "\n")


def sanitize_formula_injection(value: str) -> str:
    """Neutralize formula injection by prefixing dangerous characters with a single quote.

    When spreadsheet applications (such as Microsoft Excel, LibreOffice Calc,
    or Google Sheets) open CSV or spreadsheet files, cells starting with
    formula characters ('=', '+', '-', '@', '\\t', '\\r', '\\n') can trigger
    automatic formula evaluation or command execution (CWE-1236).

    Prefixing the value with a single quote (') forces spreadsheet engines
    to treat the cell content as literal text rather than an executable formula.

    Args:
        value: The string cell value to sanitize.

    Returns:
        The sanitized string. If the string starts with any dangerous prefix,
        it is prefixed with a single quote ('). Otherwise, the string is
        returned unchanged.

    Examples:
        >>> sanitize_formula_injection("=cmd|' /C calc'!A0")
        "'=cmd|' /C calc'!A0"
        >>> sanitize_formula_injection("DE07512108001245126162")
        'DE07512108001245126162'
    """
    if not value or not isinstance(value, str):
        return value

    if value.startswith(FORMULA_PREFIXES):
        return f"'{value}"

    return value
