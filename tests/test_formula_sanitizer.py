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

"""Tests for formula injection shielding."""

from __future__ import annotations

import pytest

from pain001.security.formula import (
    FORMULA_PREFIXES,
    sanitize_formula_injection,
)


def test_formula_prefixes_constant() -> None:
    """Ensure all dangerous formula prefixes are registered."""
    assert FORMULA_PREFIXES == ("=", "+", "-", "@", "\t", "\r", "\n")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("normal_text", "normal_text"),
        ("DE07512108001245126162", "DE07512108001245126162"),
        ("150.00", "150.00"),
        ("=cmd|' /C calc'!A0", "'=cmd|' /C calc'!A0"),
        ("+12345", "'+12345"),
        ("-12345", "'-12345"),
        ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
        ("\t=calc", "'\t=calc"),
        ("\r=calc", "'\r=calc"),
        ("\n=calc", "'\n=calc"),
        ("'=already_quoted", "'=already_quoted"),
    ],
)
def test_sanitize_formula_injection_strings(raw: str, expected: str) -> None:
    """Formula prefixes are escaped with a leading single quote."""
    assert sanitize_formula_injection(raw) == expected


def test_sanitize_formula_injection_non_string() -> None:
    """Non-string or falsy values pass through unchanged."""
    assert sanitize_formula_injection(None) is None  # type: ignore[arg-type]
    assert sanitize_formula_injection(123) == 123  # type: ignore[arg-type]
    assert sanitize_formula_injection(False) is False  # type: ignore[arg-type]
