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

"""The twin schemas follow the RA rules and accept every twin (ADR-0005)."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.corpus import get_file, list_files
from pain001.twins import (
    SUPPORTED_PREFIX,
    TwinError,
    generate_schema,
    iso_json_schema,
    to_iso_json,
    validate_iso_json,
)
from pain001.twins import schema as twin_schema

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_iso_json_schemas  # noqa: E402

EDITIONS = [v for v in valid_xml_types if v.startswith(SUPPORTED_PREFIX)]
PAIN001_FILES = [
    f for f in list_files() if f.version.startswith(SUPPORTED_PREFIX)
]
CHAPS = ("gb.chaps.property-purchase", "pain.001.001.09")


@pytest.mark.parametrize("entry", PAIN001_FILES, ids=lambda f: f.path.name)
def test_every_twin_validates(entry) -> None:
    """Market and coverage twins are valid; the coverage ones hit every path."""
    assert (
        validate_iso_json(
            to_iso_json(entry.read(), entry.version), entry.version
        )
        == []
    )


@pytest.mark.parametrize("version", EDITIONS)
def test_committed_schema_equals_a_regeneration(version: str) -> None:
    """The committed schema is byte-stable and carries the RA identity."""
    path = twin_schema.SCHEMA_DIR / f"{version}.schema.json"
    assert path.read_text(encoding="utf-8") == twin_schema.schema_text(version)
    doc = iso_json_schema(version)
    assert doc["$schema"] == twin_schema.DRAFT
    assert doc["$id"] == f"urn:iso:std:iso:20022:tech:json:{version}"
    assert doc["required"] == ["Document"]
    assert doc["$defs"]["Document"]["required"] == ["CstmrCdtTrfInitn"]
    assert doc == generate_schema(version)


def test_schema_shapes_follow_the_ra_rules() -> None:
    """Amounts, choices, repeats, booleans, decimals, dates, the envelope."""
    doc = iso_json_schema("pain.001.001.09")
    defs = doc["$defs"]
    amount = defs["ActiveOrHistoricCurrencyAndAmount"]
    assert (
        amount["required"] == ["amt", "Ccy"]
        and amount["additionalProperties"] is False
    )
    assert re.fullmatch(
        amount["properties"]["amt"]["pattern"].strip("^$"), "425000.00"
    )
    assert amount["properties"]["Ccy"]["pattern"] == "^(?:[A-Z]{3,3})$"
    choice = defs["DateAndDateTime2Choice"]
    assert choice["minProperties"] == 1 and choice["maxProperties"] == 1
    assert "required" not in choice
    message = defs["CustomerCreditTransferInitiationV09"]
    pmt = message["properties"]["PmtInf"]
    assert set(pmt) == {"anyOf"} and pmt["anyOf"][1]["type"] == "array"
    assert (
        pmt["anyOf"][1]["minItems"] == 1 and "maxItems" not in pmt["anyOf"][1]
    )
    assert message["required"] == ["GrpHdr", "PmtInf"]
    address = defs["PostalAddress24"]
    assert address["minProperties"] == 1 and "required" not in address
    assert address["properties"]["AdrLine"]["anyOf"][1]["maxItems"] == 7
    assert defs["BatchBookingIndicator"] == {
        "type": "string",
        "enum": twin_schema.BOOLEAN_VALUES,
    }
    assert defs["ISODate"]["pattern"] == twin_schema.DATE_PATTERN
    assert defs["ISODateTime"]["pattern"] == twin_schema.DATETIME_PATTERN
    assert defs["Max35Text"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 35,
    }
    assert defs["Priority2Code"]["enum"] == ["HIGH", "NORM"]
    assert defs["SupplementaryDataEnvelope1"]["type"] == "object"
    assert "additionalProperties" not in defs["SupplementaryDataEnvelope1"]


def test_schema_rejects_what_the_ra_rejects() -> None:
    """Too many decimals, a bad code, an empty component, two choice branches."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    version = CHAPS[1]

    def tx(doc):
        return doc["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["CdtTrfTxInf"][
            0
        ]

    bad = copy.deepcopy(twin)
    tx(bad)["Amt"]["InstdAmt"]["amt"] = "1.123456"
    assert any("InstdAmt/amt" in f for f in validate_iso_json(bad, version))
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["PmtMtd"] = "XYZ"
    assert any(
        "PmtMtd" in f and "not one of" in f
        for f in validate_iso_json(bad, version)
    )
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]["InitgPty"] = {}
    assert any(
        "InitgPty" in f and "non-empty" in f
        for f in validate_iso_json(bad, version)
    )
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["ReqdExctnDt"] = {
        "Dt": "2026-09-12",
        "DtTm": "2026-09-12T08:00:00",
    }
    assert any("ReqdExctnDt" in f for f in validate_iso_json(bad, version))
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["BtchBookg"] = "yes"
    assert any("BtchBookg" in f for f in validate_iso_json(bad, version))
    assert validate_iso_json({"Document": {}}, version) == [
        "/Document: 'CstmrCdtTrfInitn' is a required property"
    ]
    assert validate_iso_json({"Nope": 1}, version)[0].startswith("/: ")


def test_bare_values_validate_too() -> None:
    """The RA's single-occurrence form is accepted by the schema."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    block = twin["Document"]["CstmrCdtTrfInitn"]
    block["PmtInf"] = block["PmtInf"][0]
    block["PmtInf"]["CdtTrfTxInf"] = block["PmtInf"]["CdtTrfTxInf"][0]
    assert validate_iso_json(twin, CHAPS[1]) == []


def test_decimal_pattern_algebra() -> None:
    """Digit limits, the point forms and the sign rule."""
    p = twin_schema.decimal_pattern(
        {"total_digits": 18, "fraction_digits": 5, "min_inclusive": "0"}
    )
    for value, ok in [
        ("425000.00", True),
        ("1.12345", True),
        ("1.123456", False),
        ("-1.00", False),
        ("+0.1", True),
        ("123456789012345678", True),
        ("1234567890123456789", False),
        (".5", True),
        ("5.", True),
        ("", False),
        (".", False),
    ]:
        assert bool(re.fullmatch(p, value)) is ok, (value, ok)
    signed = twin_schema.decimal_pattern(
        {"total_digits": 18, "fraction_digits": 17}
    )
    assert re.fullmatch(signed, "-1.5") and re.fullmatch(signed, "1180.00")
    whole = twin_schema.decimal_pattern({"total_digits": 15})
    assert whole == "^[+-]?[0-9]{1,15}$"
    assert re.fullmatch(whole, "42") and not re.fullmatch(whole, "4.2")


def test_scope_and_fallbacks() -> None:
    """pain.008 is refused; a missing committed file is generated."""
    with pytest.raises(TwinError, match="pain.001"):
        iso_json_schema("pain.008.001.08")
    with pytest.raises(TwinError, match="pain.001"):
        generate_schema("pain.008.001.02")
    with pytest.raises(TwinError, match="pain.001"):
        validate_iso_json({}, "pain.008.001.02")


def test_missing_committed_schema_is_generated(monkeypatch, tmp_path) -> None:
    """Without a committed file the generated schema is served."""
    monkeypatch.setattr(twin_schema, "SCHEMA_DIR", tmp_path)
    assert iso_json_schema("pain.001.001.03") == generate_schema(
        "pain.001.001.03"
    )


def test_generator_script_check_and_write(
    monkeypatch, tmp_path, capsys
) -> None:
    """--check reports stale files; a run writes them; a second run is clean."""
    monkeypatch.setattr(twin_schema, "SCHEMA_DIR", tmp_path)
    monkeypatch.setattr(generate_iso_json_schemas, "SCHEMA_DIR", tmp_path)
    assert generate_iso_json_schemas.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "STALE" in out and "stale schema(s)" in out
    assert generate_iso_json_schemas.main([]) == 0
    assert "wrote" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.glob("*.json")) == [
        f"{v}.schema.json" for v in EDITIONS
    ]
    assert generate_iso_json_schemas.main(["--check"]) == 0
    assert "STALE" not in capsys.readouterr().out
    assert json.loads((tmp_path / "pain.001.001.03.schema.json").read_text())[
        "$id"
    ].endswith("pain.001.001.03")
