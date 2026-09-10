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

"""The one place that says which columns a payment row must carry.

Until 0.0.67 four hand-typed lists answered that question and
disagreed: a 22-column dict in the CSV validator, a 12-column dict in
the SQLite validator, a 7-column set in the editor diagnostics and the
per-version ``required`` lists in the bundled JSON schemas. A column
added to one was silently absent from the others.

The bundled schemas (``pain001/schemas/<type>.schema.json``) are the
source now. :func:`required_columns` returns, for a message type, that
schema's ``required`` list typed from its ``properties``; with no
message type it returns every column all bundled schemas describe,
which is the 22-column contract the CSV and SQLite validators always
enforced when they could not know the target version.

Types map as the validators check them: JSON ``integer`` to ``int``,
``number`` to ``float``, ``boolean`` to ``bool``, a ``string`` with a
``date`` or ``date-time`` format to :class:`datetime.datetime`, and
anything else to ``str``.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from pain001.constants import valid_xml_types

SCHEMA_DIR = Path(__file__).resolve().parent

# Keyed by the closed list of message types so a caller-supplied name
# can only ever select a bundled file, never build a path.
_SCHEMA_FILES: dict[str, Path] = {
    message_type: SCHEMA_DIR / f"{message_type}.schema.json"
    for message_type in valid_xml_types
}
_JSON_TO_PYTHON: dict[str, type] = {
    "integer": int,
    "number": float,
    "boolean": bool,
}
_DATE_FORMATS = frozenset({"date", "date-time"})

ColumnTypes = tuple[tuple[str, type], ...]


def python_type(spec: dict[str, Any]) -> type:
    """Map one JSON-schema property to the type the validators check.

    Args:
        spec: The property's schema fragment (``type``, ``format`` ...).

    Returns:
        ``int``, ``float``, ``bool``, ``datetime`` or ``str``.
    """
    json_type = spec.get("type")
    if json_type == "string" and spec.get("format") in _DATE_FORMATS:
        return datetime
    return _JSON_TO_PYTHON.get(str(json_type), str)


@cache
def _schema(message_type: str) -> dict[str, Any]:
    """Load and cache the bundled schema; callers validate the name."""
    with open(_SCHEMA_FILES[message_type], encoding="utf-8") as handle:
        schema: dict[str, Any] = json.load(handle)
    return schema


@cache
def _for_type(message_type: str) -> ColumnTypes:
    """The schema's ``required`` names, in order, with their types."""
    schema = _schema(message_type)
    properties = schema["properties"]
    return tuple(
        (name, python_type(properties[name])) for name in schema["required"]
    )


@cache
def _common() -> ColumnTypes:
    """Every column all bundled schemas describe, typed by the first."""
    schemas = [_schema(message_type) for message_type in valid_xml_types]
    shared = set.intersection(*(set(s["properties"]) for s in schemas))
    first = schemas[0]["properties"]
    return tuple(
        (name, python_type(first[name])) for name in first if name in shared
    )


def required_columns(message_type: str | None = None) -> dict[str, type]:
    """Return the columns a row must carry, with the type each must hold.

    Args:
        message_type: A bundled message type such as ``pain.001.001.09``.
            ``None`` means the target version is not known, in which
            case every column all bundled schemas describe is required.

    Returns:
        A fresh ``{column: type}`` dict, in schema order, safe to mutate.

    Raises:
        ValueError: If ``message_type`` is not a bundled message type.
    """
    if message_type is None:
        return dict(_common())
    if message_type not in _SCHEMA_FILES:
        known = ", ".join(valid_xml_types)
        raise ValueError(
            f"Unknown message type '{message_type}'. Known: {known}"
        )
    return dict(_for_type(message_type))


__all__ = ["SCHEMA_DIR", "python_type", "required_columns"]
