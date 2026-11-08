# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Every pain.001 version writes an IBAN account as ``<IBAN>`` (ADR-0011).

Until 0.0.82 the .04 to .08 templates wrote ``debtor_account_IBAN`` and
``creditor_account_IBAN`` as ``<Othr><Id>``, with no scheme name, so a
bank or validator could not tell the value was an IBAN; .03 and .09 to
.13 wrote ``<IBAN>``. A value that is not an IBAN still goes to
``<Othr><Id>``, so its output is unchanged.
"""

from __future__ import annotations

import csv
import re

import pytest
from defusedxml import ElementTree as defused_et

from pain001.constants import TEMPLATES_DIR
from pain001.xml.generate_xml import generate_xml_string

PAIN001 = [f"pain.001.001.{n:02d}" for n in range(3, 14)]
DEBTOR_IBAN = "DE89370400440532013000"
CREDITOR_IBAN = "FR1420041010050500013M02606"


def _rows(message_type: str, **values: str) -> list[dict[str, str]]:
    with (TEMPLATES_DIR / message_type / "template.csv").open(
        encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row.update(values)
    return rows


def _render(message_type: str, **values: str) -> str:
    bundle = TEMPLATES_DIR / message_type
    return generate_xml_string(
        _rows(message_type, **values),
        message_type,
        str(bundle / "template.xml"),
        str(bundle / f"{message_type}.xsd"),
    )


def _account_ids(xml: str, account: str) -> list[tuple[str, str]]:
    """``(child of Id, value)`` for every ``account`` element."""
    root = defused_et.fromstring(xml)
    found = []
    for element in root.iter():
        if element.tag.endswith("}" + account):
            ident = next(c for c in element if c.tag.endswith("}Id"))
            (child,) = list(ident)
            kind = child.tag.rpartition("}")[2]
            value = child.text if kind == "IBAN" else child[0].text
            found.append((kind, value or ""))
    return found


@pytest.mark.parametrize("message_type", PAIN001)
def test_an_iban_is_written_as_iban_in_every_version(
    message_type: str,
) -> None:
    xml = _render(
        message_type,
        debtor_account_IBAN=DEBTOR_IBAN,
        creditor_account_IBAN=CREDITOR_IBAN,
    )
    assert set(_account_ids(xml, "DbtrAcct")) == {("IBAN", DEBTOR_IBAN)}
    assert set(_account_ids(xml, "CdtrAcct")) == {("IBAN", CREDITOR_IBAN)}


@pytest.mark.parametrize("message_type", PAIN001[1:6])
@pytest.mark.parametrize(
    "value",
    ["12345678", "DE89 3704 0044 0532 0130 00", "DE00370400440532013000"],
    ids=["account-number", "spaced-iban", "bad-check-digits"],
)
def test_a_value_that_is_not_an_iban_stays_in_othr(
    message_type: str, value: str
) -> None:
    """.04 to .08 keep ``<Othr><Id>`` for anything but a valid IBAN."""
    from pain001.xml import generate_xml as gx

    bundle = TEMPLATES_DIR / message_type
    rows = _rows(message_type, debtor_account_IBAN=value)
    template, data, _ = gx._prepare_template_and_data(
        rows, message_type, str(bundle / "template.xml")
    )
    xml = template.render(**data)
    (debtor,) = set(_account_ids(xml, "DbtrAcct"))
    assert debtor == ("Othr", value)
    assert re.search(r"<Othr>\s*<Id>", xml)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (DEBTOR_IBAN, True),
        (CREDITOR_IBAN, True),
        ("DE89 3704 0044 0532 0130 00", False),
        ("de89370400440532013000", False),
        ("DE00370400440532013000", False),
        ("12345678", False),
        ("", False),
        (None, False),
        (12345678, False),
    ],
)
def test_the_iban_test(value: object, expected: bool) -> None:
    from pain001.xml._jinja import is_iban

    assert is_iban(value) is expected
