# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The schema is compiled once and reports what jsonschema.validate did.

Until 0.0.81 ``SchemaValidator.validate_data`` called
``jsonschema.validate`` for every row, which re-checks the schema
against its metaschema each time. These tests pin the two halves of
the fix: the check happens once per schema, and the message, path,
value and rule of every error match the one-shot call they replace.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from pain001.constants import valid_xml_types
from pain001.validation import schema_validator
from pain001.validation.schema_validator import SchemaValidator

_TEMPLATE_CSV = Path("pain001/templates/pain.001.001.09/template.csv")


def _reference(validator: SchemaValidator, row: dict[str, Any]) -> list[tuple]:
    """Return the error the pre-0.0.81 one-shot call reported for ``row``."""
    instance = validator._coerce_types_for_validation(row)
    try:
        jsonschema.validate(instance=instance, schema=validator.schema)
    except jsonschema.ValidationError as exc:
        path = (
            "$." + ".".join(str(p) for p in exc.absolute_path)
            if exc.absolute_path
            else "$"
        )
        return [(exc.message, path, exc.instance, str(exc.validator))]
    return []


def _base_row() -> dict[str, Any]:
    with _TEMPLATE_CSV.open(encoding="utf-8") as handle:
        return dict(next(csv.DictReader(handle)))


def _invalid_rows() -> list[dict[str, Any]]:
    """Rows that each break the schema in a different way."""
    base = _base_row()
    edits: list[dict[str, Any]] = [
        {"currency": "euro"},
        {"debtor_account_IBAN": "not an iban"},
        {"creditor_agent_BIC": "BAD"},
        {"nb_of_txs": "two"},
        {"payment_amount": "-5"},
        {"charge_bearer": "NOPE"},
        {"date": 42},
        {"currency": "euro", "creditor_agent_BIC": "BAD", "nb_of_txs": "x"},
    ]
    rows = [{**base, **edit} for edit in edits]
    missing = dict(base)
    del missing["id"]
    del missing["debtor_name"]
    rows.append(missing)
    rows.append({})
    return rows


@pytest.mark.parametrize(
    "message_type", ["pain.001.001.03", "pain.001.001.09"]
)
def test_errors_match_the_one_shot_validate(message_type: str) -> None:
    """Message, path, value and rule are those jsonschema.validate gave."""
    validator = SchemaValidator(message_type)
    for row in [_base_row(), *_invalid_rows()]:
        got = [
            (e.message, e.path, e.value, e.rule)
            for e in validator.validate_data(row)
        ]
        assert got == _reference(validator, row), row


def test_batch_order_matches_the_one_shot_validate() -> None:
    """validate_batch reports the same rows, in the same order."""
    validator = SchemaValidator("pain.001.001.09")
    rows = _invalid_rows() + [_base_row()]
    _, _, errors = validator.validate_batch(rows)
    got = [
        (index, [(e.message, e.path, e.rule) for e in row_errors])
        for index, row_errors in errors
    ]
    expected = [
        (index, [(m, p, r) for m, p, _, r in _reference(validator, row)])
        for index, row in enumerate(rows)
        if _reference(validator, row)
    ]
    assert got == expected


def test_the_schema_is_checked_once_per_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Many rows and many validators check the metaschema only once."""
    # Start cold: the conftest pins pytest's temp root, so tmp_path can
    # repeat across sessions in one process (mutmut runs several), and
    # an earlier session may already have compiled this very path.
    monkeypatch.setattr(schema_validator, "_COMPILED", {})
    name = "pain.001.001.03.schema.json"
    (tmp_path / name).write_bytes(
        (Path("pain001/schemas") / name).read_bytes()
    )
    calls: list[str] = []
    cls = jsonschema.validators.validator_for(
        SchemaValidator("pain.001.001.03").schema
    )
    original = cls.check_schema

    def counting(schema: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        calls.append("check")
        original(schema, *args, **kwargs)

    monkeypatch.setattr(cls, "check_schema", staticmethod(counting))
    rows = [_base_row()] * 50
    for _ in range(3):
        SchemaValidator("pain.001.001.03", schema_dir=tmp_path).validate_batch(
            rows
        )
    assert calls == ["check"]


def test_every_bundled_schema_compiles() -> None:
    """Each bundled schema yields a compiled validator."""
    for message_type in valid_xml_types:
        validator = SchemaValidator(message_type)
        assert validator.validate_data({}) != []


def test_an_invalid_schema_is_never_cached(tmp_path: Path) -> None:
    """A schema that fails the metaschema keeps failing, call after call."""
    (tmp_path / "pain.001.001.03.schema.json").write_text(
        json.dumps({"type": "not-a-type"}), encoding="utf-8"
    )
    validator = SchemaValidator("pain.001.001.03", schema_dir=tmp_path)
    for _ in range(2):
        with pytest.raises(ValueError, match="Invalid schema"):
            validator.validate_data({"id": "1"})
