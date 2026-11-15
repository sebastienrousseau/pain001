# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""A fresh generation reproduces every committed twin schema.

``generate_schema`` is cached, so a test that only calls it sees the
schema built the first time it was asked for. These tests drive the
generator directly, so each run of them really builds the schema from
the inventory and compares it with the committed document, whose
content the RA rules fix (ADR-0005).
"""

from __future__ import annotations

import json
import re

import pytest

from pain001.constants import valid_xml_types
from pain001.corpus import get_file
from pain001.corpus.inventory import ElementEntry, inventory_for
from pain001.twins import SUPPORTED_PREFIX, to_iso_json, validate_iso_json
from pain001.twins import schema as twin_schema

EDITIONS = [v for v in valid_xml_types if v.startswith(SUPPORTED_PREFIX)]
CHAPS = ("gb.chaps.property-purchase", "pain.001.001.09")


def _committed(version: str) -> dict[str, object]:
    """The committed schema document of an edition."""
    path = twin_schema.SCHEMA_DIR / f"{version}.schema.json"
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("version", EDITIONS)
def test_fresh_generation_equals_the_committed_schema(version: str) -> None:
    """A new generator built from the inventory reproduces the file."""
    built = twin_schema._Generator(inventory_for(version)).build()
    assert built == _committed(version)
    assert json.dumps(built, indent=2) + "\n" == (
        twin_schema.SCHEMA_DIR / f"{version}.schema.json"
    ).read_text(encoding="utf-8")


def test_generator_indexes_children_attributes_and_slots() -> None:
    """Children, the Ccy attribute and the any-slot sit under their parent."""
    generator = twin_schema._Generator(inventory_for("pain.001.001.09"))
    amount = "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Amt/InstdAmt"
    assert [a.path for a in generator.attributes[amount]] == [f"{amount}/@Ccy"]
    header = "/Document/CstmrCdtTrfInitn/GrpHdr"
    names = [c.path.rsplit("/", 1)[1] for c in generator.children[header]]
    assert names[:3] == ["MsgId", "CreDtTm", "Authstn"]
    assert all(c.kind != "attribute" for c in generator.children[header])
    assert generator.any_slots == {
        "/Document/CstmrCdtTrfInitn/SplmtryData/Envlp",
        "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/SplmtryData/Envlp",
    }
    assert "/Document/CstmrCdtTrfInitn" in generator.children
    assert generator.defs == {}


def test_ref_names_by_type_and_defines_once() -> None:
    """A type is defined on first reference and only pointed at later."""
    generator = twin_schema._Generator(inventory_for("pain.001.001.09"))
    entry = next(
        e for e in generator.inventory.elements if e.path.endswith("GrpHdr")
    )
    ref = generator._ref(entry)
    assert ref == {"$ref": f"#/$defs/{entry.type_name}"}
    first = generator.defs[str(entry.type_name)]
    assert first["required"][0] == "MsgId"
    assert generator._ref(entry) == ref
    assert generator.defs[str(entry.type_name)] is first


def test_ref_without_a_type_name_uses_the_element_name() -> None:
    """An anonymous entry is defined under its own element name."""
    generator = twin_schema._Generator(inventory_for("pain.001.001.09"))
    entry = ElementEntry(
        path="/Document/X/Anon",
        kind="simple",
        type_name=None,
        primitive="string",
        min_occurs=1,
        max_occurs=1,
        facets={"max_length": 4},
    )
    assert generator._ref(entry) == {"$ref": "#/$defs/Anon"}
    assert generator.defs["Anon"] == {"type": "string", "maxLength": 4}


def test_component_without_children_needs_one_property() -> None:
    """A complex type with no known children is a non-empty closed object."""
    generator = twin_schema._Generator(inventory_for("pain.001.001.09"))
    entry = ElementEntry(
        path="/Document/X/Empty", kind="complex", type_name="Empty1"
    )
    assert generator._define(entry) == {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "minProperties": 1,
    }


def test_decimal_defaults_and_lookahead_bound() -> None:
    """No facets means 18 whole digits; the point form counts every digit."""
    assert twin_schema.decimal_pattern({}) == "^[+-]?[0-9]{1,18}$"
    five = twin_schema.decimal_pattern(
        {"total_digits": 5, "fraction_digits": 2}
    )
    assert re.fullmatch(five, "123.45")
    assert re.fullmatch(five, "1234.5")
    assert not re.fullmatch(five, "12345.6")
    assert not re.fullmatch(five, "1234.56")


def test_findings_cut_long_messages_at_160_characters() -> None:
    """A long schema message is truncated to 160 characters in a finding."""
    twin = to_iso_json(get_file(*CHAPS), CHAPS[1])
    twin["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["PmtMtd"] = "Z" * 400
    findings = [f for f in validate_iso_json(twin, CHAPS[1]) if "PmtMtd" in f]
    assert findings
    where, message = findings[0].split(": ", 1)
    assert where.endswith("/PmtMtd")
    assert len(message) == 160
