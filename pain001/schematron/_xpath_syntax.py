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

"""Where the brackets and quotes are in a Schematron location path.

The evaluator splits a path into steps at ``/`` and a step into its
name and ``[...]`` predicates; neither split may happen inside a
predicate or a quoted string, which these helpers keep track of.
"""

from __future__ import annotations

from collections.abc import Iterator

#: Characters that end a path token outside brackets and quotes.
DELIMITERS = frozenset("(),=<>!'\"")


def scan(text: str, start: int = 0) -> Iterator[tuple[int, str, int]]:
    """Yield each index and character with its nesting level.

    The level is 0 outside every ``[...]`` predicate, the bracket depth
    inside one, and one more than that inside a quoted string there; a
    predicate's own brackets report the level outside them.
    """
    depth = 0
    quote = ""
    for index in range(start, len(text)):
        char = text[index]
        level = depth + (1 if quote else 0)
        if quote:
            quote = "" if char == quote else quote
        elif depth and char in "'\"":
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            level = depth
        yield index, char, level


def split_top(text: str, separator: str) -> list[str]:
    """Split ``text`` on ``separator`` where it is at level 0."""
    parts: list[str] = []
    begin = 0
    for index, char, level in scan(text):
        if level == 0 and char == separator:
            parts.append(text[begin:index])
            begin = index + 1
    parts.append(text[begin:])
    return [part.strip() for part in parts if part.strip()]


def step_parts(step: str) -> tuple[str, list[str]]:
    """Split a location step into its name test and its predicates."""
    predicates: list[str] = []
    begin = 0
    for index, char, level in scan(step):
        if level == 0 and char == "[":
            begin = index + 1
        elif level == 0 and char == "]":
            predicates.append(step[begin:index])
    return step.partition("[")[0].strip(), predicates


__all__ = ["DELIMITERS", "scan", "split_top", "step_parts"]
