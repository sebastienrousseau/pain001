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

"""Validating a staged file as it streams, and what a refusal says.

``collect_xsd_file_errors`` never builds the file's tree when libxml2
can read the schema. These tests pin that a broken file is still
refused with a message naming the element and the reason, in both the
detailed (small file) and the first-violation (large file) branch, and
that the fallbacks to ``xmlschema`` keep working.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from pain001.xml import publish
from pain001.xml import validate_via_xsd as module
from pain001.xml.generate_xml import generate_xml_string
from pain001.xml.validate_via_xsd import collect_xsd_file_errors

TYPE = "pain.001.001.03"
FOLDER = (Path("pain001/templates") / TYPE).resolve()
TEMPLATE = str(FOLDER / "template.xml")
XSD = str(FOLDER / f"{TYPE}.xsd")
INJECTED = "<Injected>x</Injected>"


def _rows() -> list[dict[str, Any]]:
    """The bundled .03 sample rows."""
    with (FOLDER / "template.csv").open(encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


@pytest.fixture(scope="module")
def valid_xml() -> str:
    """A schema-valid .03 document."""
    return generate_xml_string(_rows(), TYPE, TEMPLATE, XSD)


def _write(tmp_path: Path, text: str, name: str = "doc.xml") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _inject_element(xml: str) -> str:
    """Put an unknown element before the first InstdAmt."""
    at = xml.index("<InstdAmt")
    return xml[:at] + INJECTED + xml[at:]


def _bad_amount(xml: str) -> str:
    """Replace the first InstdAmt value with text."""
    start = xml.index(">", xml.index("<InstdAmt")) + 1
    end = xml.index("<", start)
    return xml[:start] + "abc" + xml[end:]


def test_a_valid_file_has_no_errors(tmp_path: Path, valid_xml: str) -> None:
    assert collect_xsd_file_errors(_write(tmp_path, valid_xml), XSD) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_inject_element, "Injected"),
        (_bad_amount, "'abc'"),
    ],
)
def test_a_small_file_lists_xmlschema_violations(
    tmp_path: Path, valid_xml: str, mutate: Any, expected: str
) -> None:
    """Below the limit, the messages are xmlschema's path and reason."""
    errors = collect_xsd_file_errors(_write(tmp_path, mutate(valid_xml)), XSD)
    assert errors
    assert "InstdAmt" in errors[0] or "Amt" in errors[0]
    assert expected in errors[0]
    assert errors[0].startswith("/")


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_inject_element, "Element 'Injected': This element is not expected"),
        (_bad_amount, "Element 'InstdAmt': 'abc' is not a valid value"),
    ],
)
def test_a_large_file_reports_libxml2s_first_violation(
    tmp_path: Path,
    valid_xml: str,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Any,
    expected: str,
) -> None:
    """Above the limit, the first violation names element and reason."""
    monkeypatch.setattr(module, "DETAILED_REPORT_LIMIT", 0)
    (error,) = collect_xsd_file_errors(
        _write(tmp_path, mutate(valid_xml)), XSD
    )
    assert error.startswith(expected)
    assert "{urn:" not in error
    assert error.endswith(
        "(first violation; the file is too large to list them all)"
    )


def _malformed(xml: str) -> dict[str, str]:
    """Documents that are not well-formed, by what is wrong."""
    return {
        "truncated": xml[: len(xml) // 2],
        "no root end": xml.rstrip()[: -len("</Document>")],
        "tag mismatch": xml.replace("</Nm>", "</Nx>", 1),
        "trailing content": xml + "<junk/>",
        "unquoted attribute": xml.replace('Ccy="', "Ccy=", 1),
        "bare ampersand": xml.replace("<Nm>", "<Nm>a & b", 1),
        "empty": "",
    }


@pytest.mark.parametrize(
    "case",
    [
        "truncated",
        "no root end",
        "tag mismatch",
        "trailing content",
        "unquoted attribute",
        "bare ampersand",
        "empty",
    ],
)
def test_a_large_malformed_file_is_refused(
    tmp_path: Path,
    valid_xml: str,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """libxml2's verdict alone still catches every well-formedness error.

    lxml with ``resolve_entities=False`` and a schema accepted the
    first, second and fifth of these; this pins the setting that
    does not.
    """
    monkeypatch.setattr(module, "DETAILED_REPORT_LIMIT", -1)
    path = _write(tmp_path, _malformed(valid_xml)[case])
    (error,) = collect_xsd_file_errors(path, XSD)
    assert "first violation" in error


ENTITY_DOCUMENT = (
    '<?xml version="1.0"?>'
    '<!DOCTYPE Document [<!ENTITY a "aaaaaaaaaa">]>'
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">'
    "&a;</Document>"
)


def test_a_declared_entity_is_refused_before_the_schema_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DTD is refused up front; libxml2 crashes on one under a schema."""
    monkeypatch.setattr(module, "DETAILED_REPORT_LIMIT", -1)
    (error,) = collect_xsd_file_errors(_write(tmp_path, ENTITY_DOCUMENT), XSD)
    assert error.startswith("the document declares a DTD")


def test_a_small_file_with_a_dtd_goes_to_xmlschema(
    tmp_path: Path,
) -> None:
    """xmlschema (defused) refuses the entity declaration itself."""
    errors = collect_xsd_file_errors(_write(tmp_path, ENTITY_DOCUMENT), XSD)
    assert errors[0].startswith("XML parse error: EntitiesForbidden")


def test_xmlschema_decides_a_small_file_libxml2_rejects(
    tmp_path: Path, valid_xml: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A libxml2 rejection of a small file is not final, as for strings."""
    monkeypatch.setattr(
        module, "_lxml_first_file_error", lambda path, schema: "refused"
    )
    assert collect_xsd_file_errors(_write(tmp_path, valid_xml), XSD) == []


def test_a_schema_libxml2_cannot_compile_falls_back(
    tmp_path: Path, valid_xml: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """xmlschema reads the file when libxml2 cannot use the schema."""

    def refuse(path: str) -> None:
        raise ValueError("unsupported")

    monkeypatch.setattr(module, "_get_cached_lxml_schema", refuse)
    path = _write(tmp_path, _inject_element(valid_xml))
    (error, *_rest) = collect_xsd_file_errors(path, XSD)
    assert "Injected" in error
    assert (
        collect_xsd_file_errors(_write(tmp_path, valid_xml, "ok.xml"), XSD)
        == []
    )


def test_without_lxml_xmlschema_reads_the_file(
    tmp_path: Path, valid_xml: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "_LXML_AVAILABLE", False)
    path = _write(tmp_path, _bad_amount(valid_xml))
    assert "abc" in collect_xsd_file_errors(path, XSD)[0]


def test_elements_are_released_as_they_are_validated(
    tmp_path: Path, valid_xml: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every finished element is cleared, so no tree builds up."""
    released: list[int] = []
    real = module._release

    def spy(element: Any) -> None:
        real(element)
        released.append(len(element))

    monkeypatch.setattr(module, "_release", spy)
    collect_xsd_file_errors(_write(tmp_path, valid_xml), XSD)
    assert released and set(released) == {0}


def test_the_staged_check_names_the_violation(
    tmp_path: Path, valid_xml: str
) -> None:
    """The publish check raises with the schema and the reason."""
    check = publish.xsd_check(XSD, TYPE)
    with pytest.raises(
        RuntimeError, match="failed validation against.*Injected"
    ):
        check(_write(tmp_path, _inject_element(valid_xml)))
    check(_write(tmp_path, valid_xml, "ok.xml"))
