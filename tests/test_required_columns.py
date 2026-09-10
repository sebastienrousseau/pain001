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

"""One required-column contract, derived from the bundled JSON schemas.

The CSV validator, the SQLite validator and the editor diagnostics used
to carry their own lists. These tests pin the shared source to the
schemas, pin the version-agnostic set to the 22 columns the validators
always enforced, and check the three consumers agree.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.csv.validate_csv_data import validate_csv_data
from pain001.db.validate_db_data import validate_db_data
from pain001.lsp.diagnostics import _required_columns, diagnostics_for_csv
from pain001.schemas.required_columns import (
    SCHEMA_DIR,
    python_type,
    required_columns,
)
from pain001.validation import required_columns as exported

TEMPLATES = Path(__file__).resolve().parent.parent / "pain001" / "templates"

# The contract the CSV validator enforced by hand before 0.0.67, in its
# original order. Only ``id`` changed type: the schemas (and the XSD's
# Max35Text MsgId) say string, the old dict said int.
HISTORICAL_CONTRACT: dict[str, type] = {
    "id": str,
    "date": datetime,
    "nb_of_txs": int,
    "ctrl_sum": float,
    "initiator_name": str,
    "payment_information_id": str,
    "payment_method": str,
    "batch_booking": bool,
    "service_level_code": str,
    "requested_execution_date": datetime,
    "debtor_name": str,
    "debtor_account_IBAN": str,
    "debtor_agent_BIC": str,
    "forwarding_agent_BIC": str,
    "charge_bearer": str,
    "payment_id": str,
    "payment_amount": float,
    "currency": str,
    "creditor_agent_BIC": str,
    "creditor_name": str,
    "creditor_account_IBAN": str,
    "remittance_information": str,
}


def _schema(message_type: str) -> dict:
    with open(SCHEMA_DIR / f"{message_type}.schema.json") as handle:
        return json.load(handle)


def test_version_agnostic_set_is_the_historical_contract() -> None:
    """With no message type the 22 historical columns are required."""
    assert required_columns() == HISTORICAL_CONTRACT
    assert list(required_columns()) == list(HISTORICAL_CONTRACT)


def test_exported_from_the_validation_package() -> None:
    """``pain001.validation.required_columns`` is the same callable."""
    assert exported is required_columns


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_per_version_set_is_the_schema_required_list(
    message_type: str,
) -> None:
    """Names and order come from the schema's ``required``."""
    schema = _schema(message_type)
    columns = required_columns(message_type)
    assert list(columns) == schema["required"]
    for name, kind in columns.items():
        assert kind is python_type(schema["properties"][name])


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_bundled_template_csv_satisfies_its_schema(
    message_type: str,
) -> None:
    """Every template.csv carries every column its schema requires."""
    with open(TEMPLATES / message_type / "template.csv", newline="") as fh:
        header = set(next(csv.reader(fh)))
    assert set(required_columns(message_type)) <= header


def test_schemas_agree_on_types_for_shared_columns() -> None:
    """A column means the same type in every schema that describes it."""
    seen: dict[str, type] = {}
    for message_type in valid_xml_types:
        for name, spec in _schema(message_type)["properties"].items():
            kind = python_type(spec)
            assert seen.setdefault(name, kind) is kind, (
                f"{name} is {kind.__name__} in {message_type} but "
                f"{seen[name].__name__} elsewhere"
            )


def test_unknown_message_type_is_rejected() -> None:
    """A name outside the bundled list raises, it never builds a path."""
    with pytest.raises(ValueError, match="Unknown message type"):
        required_columns("../../etc/passwd")


def test_returned_dict_is_a_copy() -> None:
    """Mutating a result does not leak into the cached contract."""
    first = required_columns("pain.001.001.03")
    first["injected"] = str
    assert "injected" not in required_columns("pain.001.001.03")


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ({"type": "integer"}, int),
        ({"type": "number"}, float),
        ({"type": "boolean"}, bool),
        ({"type": "string", "format": "date"}, datetime),
        ({"type": "string", "format": "date-time"}, datetime),
        ({"type": "string"}, str),
        ({"type": "string", "format": "email"}, str),
        ({}, str),
    ],
)
def test_python_type_mapping(spec: dict, expected: type) -> None:
    """JSON types map to the types ``_validate_field_type`` checks."""
    assert python_type(spec) is expected


def _row(names: dict[str, type]) -> dict[str, str]:
    samples = {
        int: "2",
        float: "10.00",
        bool: "true",
        datetime: "2026-01-02",
        str: "x",
    }
    return {name: samples[kind] for name, kind in names.items()}


def test_csv_validator_uses_the_per_version_contract() -> None:
    """A .09 row with only the 13 schema columns passes for .09 only."""
    row = _row(required_columns("pain.001.001.09"))
    assert validate_csv_data([row], "pain.001.001.09") is True
    assert validate_csv_data([row]) is False
    assert validate_csv_data([row], "pain.008.001.02") is False


def test_csv_validator_accepts_a_textual_id() -> None:
    """``id`` is Max35Text in the XSD, so ``MSG001`` is valid."""
    row = _row(required_columns())
    row["id"] = "MSG001"
    assert validate_csv_data([row]) is True


def test_db_validator_shares_the_contract() -> None:
    """The SQLite validator reaches the same verdicts as the CSV one."""
    row = _row(required_columns("pain.008.001.02"))
    assert validate_db_data([row], "pain.008.001.02") is True
    assert validate_db_data([row]) is validate_csv_data([row])
    row.pop("mandate_id")
    assert validate_db_data([row], "pain.008.001.02") is False


def test_lsp_diagnostics_share_the_contract() -> None:
    """The editor reports exactly the schema's missing columns."""
    assert _required_columns("pain.001.001.09") == set(
        required_columns("pain.001.001.09")
    )
    assert _required_columns("not-bundled") == set(required_columns())
    header = ",".join(required_columns("pain.001.001.09"))
    missing = {
        d.message
        for d in diagnostics_for_csv(header, "pain.001.001.03")
        if d.code == "missing-column"
    }
    expected = set(required_columns("pain.001.001.03")) - set(
        required_columns("pain.001.001.09")
    )
    assert missing == {f"Missing required column: {n!r}" for n in expected}
