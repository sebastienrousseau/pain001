# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The row-to-template mappings of the legacy message types.

``_prepare_xml_data_v04``, ``_v05_to_v08`` and ``_v08_direct_debit``
copy input columns into the variables their ``template.xml`` renders.
The bundled samples fill every column, so a misspelt column or a wrong
default renders the same XML for them and no golden file notices. These
tests pin the mapping to the repository's own references instead of
restating it: the columns the bundled ``template.csv`` files define, the
variables each ``template.xml`` uses, and the scheme defaults below.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.xml import message_registry as registry

Prepare = Callable[[list[dict[str, Any]]], dict[str, Any]]

# The defaults a type applies when a column is absent, by output path.
# Every other value of an empty row must be "".
_CASES: list[tuple[str, Prepare, dict[tuple[Any, ...], str]]] = [
    (
        "pain.001.001.04",
        registry._prepare_xml_data_v04,
        {("transactions", 0, "payment_currency"): "EUR"},
    ),
    (
        "pain.001.001.05",
        registry._prepare_xml_data_v05_to_v08,
        {
            ("service_level_code",): "SEPA",
            ("payment_method",): "TRF",
            ("batch_booking",): "false",
            ("transactions", 0, "charge_bearer"): "SLEV",
        },
    ),
    (
        "pain.008.001.08",
        registry._prepare_xml_data_v08_direct_debit,
        {
            ("payment_method",): "DD",
            ("batch_booking",): "false",
            ("service_level_code",): "SEPA",
            ("sequence_type",): "RCUR",
            ("charge_bearer",): "SLEV",
            ("transactions", 0, "payment_currency"): "EUR",
            ("transactions", 0, "sequence_type"): "RCUR",
        },
    ),
]
_IDS = [case[0] for case in _CASES]

# Accepted as a fallback for ``initiator_town_name`` by .05 to .08.
_LEGACY_ALIASES = {"initiator_town"}


class _RecordingRow:
    """A row that has every column: it records each one read and
    answers ``<prefix>:<column>``. The prepare functions only call
    ``get``, ``[]`` and ``in`` on a row, so it need not be a dict."""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.read: set[str] = set()

    def get(self, key: str, default: Any = None) -> str:
        self.read.add(key)
        return f"{self.prefix}:{key}"

    def __getitem__(self, key: str) -> str:
        return self.get(key)

    def __contains__(self, key: object) -> bool:
        self.read.add(str(key))
        return True


def _rows(*rows: _RecordingRow) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", list(rows))


def _leaves(
    value: Any, path: tuple[Any, ...] = ()
) -> Iterator[tuple[tuple[Any, ...], Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, (*path, index))
    else:
        yield path, value


def _template_columns() -> set[str]:
    columns: set[str] = set()
    for path in TEMPLATES_DIR.glob("*/template.csv"):
        with path.open(encoding="utf-8") as handle:
            columns.update(next(csv.reader(handle)))
    return columns


def _template_variables(message_type: str) -> tuple[set[str], set[str]]:
    """Top-level names and ``tx.<name>`` attributes the template uses."""
    source = (TEMPLATES_DIR / message_type / "template.xml").read_text(
        encoding="utf-8"
    )
    names = set(re.findall(r"{{\s*([A-Za-z_][\w.]*)", source))
    names |= set(
        re.findall(r"{%\s*(?:if|elif|for \w+ in)\s+([A-Za-z_][\w.]*)", source)
    )
    loop = set(re.findall(r"{%\s*for (\w+) in", source))
    top = {name.split(".")[0] for name in names} - loop
    attributes = {
        name.split(".", 1)[1]
        for name in names
        if "." in name and name.split(".")[0] in loop
    }
    return top, attributes


@pytest.mark.parametrize(
    ("message_type", "prepare", "defaults"), _CASES, ids=_IDS
)
def test_every_column_read_is_a_known_column(
    message_type: str, prepare: Prepare, defaults: dict[Any, str]
) -> None:
    row = _RecordingRow("r0")
    prepare(_rows(row))
    unknown = row.read - _template_columns() - _LEGACY_ALIASES
    assert not unknown, f"{message_type} reads unknown columns {unknown}"


@pytest.mark.parametrize(
    ("message_type", "prepare", "defaults"), _CASES, ids=_IDS
)
def test_every_template_variable_is_provided(
    message_type: str, prepare: Prepare, defaults: dict[Any, str]
) -> None:
    result = prepare(_rows(_RecordingRow("r0")))
    top, attributes = _template_variables(message_type)
    assert top <= set(result), top - set(result)
    for transaction in result["transactions"]:
        assert attributes <= set(transaction), attributes - set(transaction)


@pytest.mark.parametrize(
    ("message_type", "prepare", "defaults"), _CASES, ids=_IDS
)
def test_an_empty_row_gives_only_the_scheme_defaults(
    message_type: str, prepare: Prepare, defaults: dict[Any, str]
) -> None:
    found = {
        path: value for path, value in _leaves(prepare([{}])) if value != ""
    }
    assert found == defaults


@pytest.mark.parametrize(
    ("message_type", "prepare", "defaults"), _CASES, ids=_IDS
)
def test_each_value_comes_from_its_own_row(
    message_type: str, prepare: Prepare, defaults: dict[Any, str]
) -> None:
    """Message-level values come from the first row; each transaction
    from its own row, in order."""
    result = prepare(_rows(_RecordingRow("r0"), _RecordingRow("r1")))
    assert len(result["transactions"]) == 2
    for path, value in _leaves(result):
        expected = f"r{path[1]}:" if path[0] == "transactions" else "r0:"
        assert str(value).startswith(expected), (path, value)
