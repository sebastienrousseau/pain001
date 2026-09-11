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

"""The ISO JSON twin is lossless and follows the RA 2025 shape (ADR-0005)."""

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET

import pytest

from pain001.corpus import get_file, list_files
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.twins import (
    SUPPORTED_PREFIX,
    TwinError,
    from_iso_json,
    iso_json,
    supported,
    to_iso_json,
)
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

PAIN001_FILES = [
    f for f in list_files() if f.version.startswith(SUPPORTED_PREFIX)
]
CHAPS = ("gb.chaps.property-purchase", "pain.001.001.09")


def _canon(xml: str):
    """Tag, text, attributes and children, whitespace ignored."""

    def walk(element):
        return (
            element.tag,
            (element.text or "").strip(),
            tuple(sorted(element.attrib.items())),
            tuple(walk(child) for child in element),
        )

    return walk(ET.fromstring(xml.encode("utf-8")))


def _walk(node, path=""):
    """Every (path, value) pair of a twin, arrays flattened."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, path)
    else:
        yield path, node


@pytest.mark.parametrize("entry", PAIN001_FILES, ids=lambda f: f.path.name)
def test_every_pain001_file_round_trips(entry) -> None:
    """Market and coverage files come back element for element."""
    xml = entry.read()
    twin = to_iso_json(xml, entry.version)
    back = from_iso_json(twin, entry.version)
    assert _canon(back) == _canon(xml)
    xsd = str(DEFAULT_TEMPLATE_REGISTRY.get_template(entry.version).xsd_path)
    assert validate_xml_string_via_xsd(back, xsd)
    assert json.dumps(twin) == json.dumps(to_iso_json(back, entry.version)), (
        "the twin of the round-tripped XML is the same twin"
    )


def test_twin_has_the_ra_shape() -> None:
    """Document root, tag names, amt/Ccy amounts, string booleans, no @ or $."""
    xml = get_file(*CHAPS)
    twin = to_iso_json(xml, CHAPS[1])
    assert set(twin) == {"Document"}
    root = twin["Document"]
    assert set(root) == {"CstmrCdtTrfInitn"}
    pmt = root["CstmrCdtTrfInitn"]["PmtInf"]
    assert isinstance(pmt, list) and len(pmt) == 1, (
        "repeatable: always an array"
    )
    tx = pmt[0]["CdtTrfTxInf"]
    assert isinstance(tx, list)
    assert tx[0]["Amt"] == {"InstdAmt": {"amt": "425000.00", "Ccy": "GBP"}}
    assert pmt[0]["BtchBookg"] == "false"
    assert pmt[0]["PmtTpInf"]["SvcLvl"] == [{"Cd": "SDVA"}]
    for path, value in _walk(twin):
        assert "@" not in path and "$" not in path, path
        assert isinstance(value, str), (path, value)
    text = json.dumps(twin)
    assert "xmlns" not in text


def test_decoder_accepts_bare_values_and_boolean_forms() -> None:
    """A single occurrence may be a bare value; booleans may be 1/0."""
    xml = get_file(*CHAPS)
    twin = to_iso_json(xml, CHAPS[1])
    loose = copy.deepcopy(twin)
    block = loose["Document"]["CstmrCdtTrfInitn"]
    block["PmtInf"] = block["PmtInf"][0]
    block["PmtInf"]["BtchBookg"] = "0"
    block["PmtInf"]["CdtTrfTxInf"] = block["PmtInf"]["CdtTrfTxInf"][0]
    assert _canon(from_iso_json(loose, CHAPS[1])) == _canon(xml)
    block["PmtInf"]["BtchBookg"] = "1"
    assert "<BtchBookg>true</BtchBookg>" in from_iso_json(loose, CHAPS[1])
    block["PmtInf"]["BtchBookg"] = "yes"
    with pytest.raises(TwinError, match="not a boolean"):
        from_iso_json(loose, CHAPS[1])


def test_decoder_orders_children_by_the_schema() -> None:
    """Keys in any order encode to a schema-ordered, valid document."""
    xml = get_file(*CHAPS)
    twin = to_iso_json(xml, CHAPS[1])
    header = twin["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]
    shuffled = dict(reversed(list(header.items())))
    twin["Document"]["CstmrCdtTrfInitn"]["GrpHdr"] = shuffled
    back = from_iso_json(twin, CHAPS[1])
    assert _canon(back) == _canon(xml)
    assert back.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<Document')


def test_twin_rejects_what_the_edition_rejects() -> None:
    """Unknown elements, bad facets and a wrong root raise TwinError."""
    xml = get_file(*CHAPS)
    twin = to_iso_json(xml, CHAPS[1])
    with pytest.raises(TwinError, match="single key"):
        from_iso_json(twin["Document"], CHAPS[1])
    with pytest.raises(TwinError, match="single key"):
        from_iso_json(["nope"], CHAPS[1])  # type: ignore[arg-type]
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]["Nope"] = "x"
    with pytest.raises(TwinError, match="does not fit"):
        from_iso_json(bad, CHAPS[1])
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]["MsgId"] = "x" * 36
    with pytest.raises(TwinError, match="does not fit"):
        from_iso_json(bad, CHAPS[1])
    with pytest.raises(TwinError, match="not a valid"):
        to_iso_json("<Document/>", CHAPS[1])


def test_scope_is_bundled_pain001_editions_only() -> None:
    """pain.008 and unknown editions are refused (ADR-0005 scope)."""
    assert supported("pain.001.001.03") and supported("pain.001.001.13")
    assert not supported("pain.008.001.08")
    assert not supported("pain.001.001.99")
    xml = get_file("gb.bacs-dd.collection", "pain.008.001.08")
    with pytest.raises(TwinError, match="pain.001"):
        to_iso_json(xml, "pain.008.001.08")
    with pytest.raises(TwinError, match="pain.001"):
        from_iso_json({"Document": {}}, "pain.008.001.08")


def test_always_array_normalisation_is_ours() -> None:
    """A bare value for a repeatable element is wrapped on the way out.

    The converter already lists repeatable elements, so this guards the
    rule itself: whatever the converter does, the twin is always-array.
    """
    repeatable, booleans = iso_json._shape("pain.001.001.09")
    assert "CstmrCdtTrfInitn/PmtInf" in repeatable
    assert "CstmrCdtTrfInitn/PmtInf/BtchBookg" in booleans
    raw = {
        "CstmrCdtTrfInitn": {
            "PmtInf": {"PmtInfId": "P1", "BtchBookg": True},
            "GrpHdr": {"MsgId": "M1"},
        }
    }
    twin = iso_json._encode_node(raw, "", repeatable)
    assert twin["CstmrCdtTrfInitn"]["PmtInf"] == [
        {"PmtInfId": "P1", "BtchBookg": "true"}
    ]
    assert iso_json._encode_node([True, False], "x", repeatable) == [
        "true",
        "false",
    ]


EMPTY_COMPONENTS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09">'
    "<CstmrCdtTrfInitn><GrpHdr><MsgId>M</MsgId>"
    "<CreDtTm>2026-01-02T09:00:00</CreDtTm><NbOfTxs>1</NbOfTxs>"
    "<InitgPty/></GrpHdr><PmtInf><PmtInfId>P</PmtInfId><PmtMtd>TRF</PmtMtd>"
    "<ReqdExctnDt><Dt>2026-01-02</Dt></ReqdExctnDt><Dbtr/>"
    "<DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>"
    "<DbtrAgt><FinInstnId/></DbtrAgt><CdtTrfTxInf><PmtId><EndToEndId>E"
    '</EndToEndId></PmtId><Amt><InstdAmt Ccy="EUR">1.00</InstdAmt></Amt>'
    "<Cdtr/></CdtTrfTxInf></PmtInf></CstmrCdtTrfInitn></Document>"
)


def test_empty_components_stay_lossless() -> None:
    """The XSD allows an empty component; the twin keeps it as {}."""
    twin = to_iso_json(EMPTY_COMPONENTS, "pain.001.001.09")
    header = twin["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]
    assert header["InitgPty"] == {}
    pmt = twin["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]
    assert pmt["Dbtr"] == {} and pmt["DbtrAgt"] == {"FinInstnId": {}}
    back = from_iso_json(twin, "pain.001.001.09")
    assert _canon(back) == _canon(EMPTY_COMPONENTS)
    assert "<InitgPty />" in back or "<InitgPty/>" in back
