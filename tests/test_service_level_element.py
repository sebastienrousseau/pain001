# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The .04 to .08 templates write ``service_level_code`` (ADR-0011).

Until 0.0.82 they had no ``PmtTpInf``, so a service level in the input
was dropped and a SEPA file failed EPC-PMT-002. They now write
``PmtTpInf/SvcLvl/Cd`` on the batch, as .03 and .09 to .13 do, and only
when the column has a value: input without it renders as before.
"""

from __future__ import annotations

import csv

import pytest
from defusedxml import ElementTree as defused_et

from pain001.constants import TEMPLATES_DIR
from pain001.schematron import validate_schematron
from pain001.xml.generate_xml import generate_xml_string

LEGACY = [f"pain.001.001.{n:02d}" for n in range(4, 9)]


def _rows(message_type: str, **values: str) -> list[dict[str, str]]:
    with (TEMPLATES_DIR / message_type / "template.csv").open(
        encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row.update(values)
    return rows


def _render(message_type: str, rows: list[dict[str, str]]) -> str:
    bundle = TEMPLATES_DIR / message_type
    return generate_xml_string(
        rows,
        message_type,
        str(bundle / "template.xml"),
        str(bundle / f"{message_type}.xsd"),
    )


def _batch_children(xml: str) -> list[str]:
    root = defused_et.fromstring(xml)
    (batch,) = (e for e in root.iter() if e.tag.endswith("}PmtInf"))
    return [child.tag.rpartition("}")[2] for child in batch]


def _service_levels(xml: str) -> list[str]:
    root = defused_et.fromstring(xml)
    return [
        (code.text or "")
        for level in root.iter()
        if level.tag.endswith("}SvcLvl")
        for code in level
        if code.tag.endswith("}Cd")
    ]


@pytest.mark.parametrize("message_type", LEGACY)
def test_a_service_level_is_written_on_the_batch(message_type: str) -> None:
    xml = _render(message_type, _rows(message_type, service_level_code="SEPA"))
    children = _batch_children(xml)
    position = children.index("PmtTpInf")
    assert children[position - 1] == "BtchBookg"
    assert children[position + 1] == "ReqdExctnDt"
    assert _service_levels(xml) == ["SEPA"]


@pytest.mark.parametrize("message_type", LEGACY)
@pytest.mark.parametrize("absent", ["empty", "missing"])
def test_no_service_level_writes_no_payment_type(
    message_type: str, absent: str
) -> None:
    rows = _rows(message_type, service_level_code="")
    if absent == "missing":
        for row in rows:
            del row["service_level_code"]
    xml = _render(message_type, rows)
    assert "PmtTpInf" not in _batch_children(xml)
    assert "<SvcLvl>" not in xml


@pytest.mark.parametrize("message_type", LEGACY[1:])
def test_the_sepa_samples_pass_the_epc_rulebook(message_type: str) -> None:
    """.05 to .08 ship SEPA samples; .04's uses SHAR and INST on purpose."""
    xml = _render(message_type, _rows(message_type))
    result = validate_schematron(xml, rulebook="sepa")
    assert result.violations == []
    assert result.rules_evaluated > 0
