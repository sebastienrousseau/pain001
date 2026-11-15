# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Business Application Header and envelope: structure, prefixes, round trip.

The receiving bank validates the envelope against head.001 and head.003,
so the element paths, the generated identifiers and the namespace
prefixes are pinned here, together with what unpacking gives back.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as et
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from pain001.xml.envelope import (
    BAH_NAMESPACE,
    BIZDATA_NAMESPACE,
    XML_DSIG_NAMESPACE,
    BusinessApplicationHeader,
    envelop_iso20022_message,
    unpack_iso20022_message,
)

PAIN_09 = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
DOC_09 = (
    f'<Document xmlns="{PAIN_09}"><CstmrCdtTrfInitn><GrpHdr>'
    "<MsgId>MSG-009</MsgId></GrpHdr></CstmrCdtTrfInitn></Document>"
)


def _bah(*names: str) -> str:
    """The Clark-notation path of ``names`` in the BAH namespace."""
    return "/".join(f"{{{BAH_NAMESPACE}}}{name}" for name in names)


def _signature() -> et.Element:
    """A minimal ds:Signature element to carry in the header."""
    sig = et.Element(f"{{{XML_DSIG_NAMESPACE}}}Signature")
    et.SubElement(sig, f"{{{XML_DSIG_NAMESPACE}}}SignedInfo")
    return sig


@pytest.fixture
def tokyo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run with a local time zone nine hours ahead of UTC."""
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_generated_identifier_is_msg_and_sixteen_upper_hex() -> None:
    """A missing BizMsgIdr is generated as ``MSG-`` and 16 hex digits."""
    for _ in range(8):
        text = (
            BusinessApplicationHeader()
            .to_element()
            .findtext(_bah("BizMsgIdr"))
        )
        assert re.fullmatch(r"MSG-[0-9A-F]{16}", text or "")


@pytest.mark.usefixtures("tokyo")
def test_generated_creation_time_is_utc() -> None:
    """A missing CreDt is the current UTC time, ISO 8601 with ``Z``."""
    element = BusinessApplicationHeader().to_element()
    text = element.findtext(_bah("CreDt")) or ""
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", text)
    created = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert abs((datetime.now(UTC) - created).total_seconds()) < 120


def test_party_paths_follow_head_001() -> None:
    """An organisation id and a BIC each sit at their schema path."""
    element = BusinessApplicationHeader(
        from_id="ACME-ORG-1", to_bic="DEUTDEFFXXX"
    ).to_element()
    org = element.find(_bah("Fr", "OrgId", "Id", "OrgId", "Othr", "Id"))
    assert org is not None and org.text == "ACME-ORG-1"
    bic = element.find(_bah("To", "FIId", "FinInstnId", "BICFI"))
    assert bic is not None and bic.text == "DEUTDEFFXXX"


def test_envelope_default_is_wrapped_with_prefixes() -> None:
    """By default AppHdr sits in Hdr and the Document in Pyld."""
    header = BusinessApplicationHeader(
        from_bic="DEUTDEFFXXX", to_bic="COBADEFFXXX", signature=_signature()
    )
    xml = envelop_iso20022_message(DOC_09, header)
    root = et.fromstring(xml)
    assert [child.tag for child in root] == [
        f"{{{BIZDATA_NAMESPACE}}}Hdr",
        f"{{{BIZDATA_NAMESPACE}}}Pyld",
    ]
    assert root[0][0].tag == f"{{{BAH_NAMESPACE}}}AppHdr"
    assert root[1][0].tag == f"{{{PAIN_09}}}Document"
    assert "<head:AppHdr>" in xml
    assert f'xmlns:head="{BAH_NAMESPACE}"' in xml
    assert "<doc:Document>" in xml
    assert f'xmlns:doc="{PAIN_09}"' in xml
    assert "<ds:Signature>" in xml
    assert f'xmlns:ds="{XML_DSIG_NAMESPACE}"' in xml
    assert "ns0:" not in xml


def test_message_definition_is_inferred_only_when_absent() -> None:
    """The document's own namespace fills a missing MsgDefIdr only."""
    inferred = BusinessApplicationHeader()
    envelop_iso20022_message(DOC_09, inferred)
    assert inferred.msg_def_idr == "pain.001.001.09"
    explicit = BusinessApplicationHeader(msg_def_idr="pain.001.001.03")
    xml = envelop_iso20022_message(DOC_09, explicit)
    assert explicit.msg_def_idr == "pain.001.001.03"
    found = et.fromstring(xml).find(f".//{_bah('MsgDefIdr')}")
    assert found is not None and found.text == "pain.001.001.03"


def test_unpack_returns_the_document_with_its_default_namespace() -> None:
    """The payload comes back as a standalone, default-namespaced Document."""
    header = BusinessApplicationHeader(from_bic="DEUTDEFFXXX")
    xml = envelop_iso20022_message(DOC_09, header)
    unpacked, document = unpack_iso20022_message(xml.encode("utf-8"))
    assert unpacked is not None
    assert document.startswith(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<Document xmlns="{PAIN_09}">'
    )
    root = et.fromstring(document.split("\n", 1)[1])
    assert root.tag == f"{{{PAIN_09}}}Document"
    assert root.findtext(f".//{{{PAIN_09}}}MsgId") == "MSG-009"


def test_header_signature_round_trips() -> None:
    """The one element inside Sgntr is returned as the header signature."""
    header = BusinessApplicationHeader(signature=_signature())
    unpacked, _ = unpack_iso20022_message(
        envelop_iso20022_message(DOC_09, header)
    )
    assert unpacked is not None
    assert isinstance(unpacked.signature, str)
    parsed = et.fromstring(unpacked.signature)
    assert parsed.tag == f"{{{XML_DSIG_NAMESPACE}}}Signature"
    assert parsed[0].tag == f"{{{XML_DSIG_NAMESPACE}}}SignedInfo"


def test_only_sgntr_fills_the_signature() -> None:
    """Other header children with content never become a signature."""
    xml = (
        f'<BizData xmlns="{BIZDATA_NAMESPACE}"><Hdr>'
        f'<AppHdr xmlns="{BAH_NAMESPACE}"><BizMsgIdr>B-1</BizMsgIdr>'
        "<Rltd><BizMsgIdr>B-0</BizMsgIdr></Rltd></AppHdr></Hdr>"
        f"<Pyld>{DOC_09}</Pyld></BizData>"
    )
    unpacked, _ = unpack_iso20022_message(xml)
    assert unpacked is not None
    assert unpacked.biz_msg_idr == "B-1"
    assert unpacked.signature is None
