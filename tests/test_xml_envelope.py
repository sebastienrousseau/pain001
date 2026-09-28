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

"""Unit tests for ISO 20022 Business Application Header (head.001) and Envelope."""

import xml.etree.ElementTree as et

from pain001.xml.envelope import (
    BAH_NAMESPACE,
    BIZDATA_NAMESPACE,
    BusinessApplicationHeader,
    envelop_iso20022_message,
    extract_msg_def_idr,
    unpack_iso20022_message,
)

SAMPLE_DOC_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">\n'
    "  <CstmrCdtTrfInitn>\n"
    "    <GrpHdr>\n"
    "      <MsgId>MSG-001</MsgId>\n"
    "      <CreDtTm>2026-09-26T21:00:00</CreDtTm>\n"
    "      <NbOfTxs>1</NbOfTxs>\n"
    "      <InitgPty><Nm>Acme Corp</Nm></InitgPty>\n"
    "    </GrpHdr>\n"
    "  </CstmrCdtTrfInitn>\n"
    "</Document>"
)


def test_default_bah_element_creation() -> None:
    """Verify default BAH element has expected namespace and required defaults."""
    header = BusinessApplicationHeader()
    element = header.to_element()

    assert element.tag == f"{{{BAH_NAMESPACE}}}AppHdr"
    assert element.find(f".//{{{BAH_NAMESPACE}}}BICFI").text == "NOTPROVIDED"
    assert (
        element.find(f".//{{{BAH_NAMESPACE}}}MsgDefIdr").text
        == "pain.001.001.03"
    )
    assert element.find(f".//{{{BAH_NAMESPACE}}}BizMsgIdr").text.startswith(
        "MSG-"
    )
    assert element.find(f".//{{{BAH_NAMESPACE}}}CreDt") is not None


def test_custom_bah_properties() -> None:
    """Verify all custom header fields are properly constructed in XML."""
    header = BusinessApplicationHeader(
        from_bic="SNDRBEBBXXX",
        to_bic="RCVRUS33XXX",
        biz_msg_idr="BIZ-MSG-2026-9999",
        msg_def_idr="pain.008.001.02",
        cre_dt="2026-09-26T12:00:00Z",
        char_set="UTF-8",
        biz_svc="sepa.sct",
        cpy_dplct="COPY",
        pssbl_dplct=True,
        prty="HIGH",
    )
    el = header.to_element()

    assert el.find(f".//{{{BAH_NAMESPACE}}}CharSet").text == "UTF-8"
    assert (
        el.find(f"{{{BAH_NAMESPACE}}}Fr//{{{BAH_NAMESPACE}}}BICFI").text
        == "SNDRBEBBXXX"
    )
    assert (
        el.find(f"{{{BAH_NAMESPACE}}}To//{{{BAH_NAMESPACE}}}BICFI").text
        == "RCVRUS33XXX"
    )
    assert el.find(f"{{{BAH_NAMESPACE}}}BizMsgIdr").text == "BIZ-MSG-2026-9999"
    assert el.find(f"{{{BAH_NAMESPACE}}}MsgDefIdr").text == "pain.008.001.02"
    assert el.find(f"{{{BAH_NAMESPACE}}}BizSvc").text == "sepa.sct"
    assert el.find(f"{{{BAH_NAMESPACE}}}CreDt").text == "2026-09-26T12:00:00Z"
    assert el.find(f"{{{BAH_NAMESPACE}}}CpyDplct").text == "COPY"
    assert el.find(f"{{{BAH_NAMESPACE}}}PssblDplct").text == "true"
    assert el.find(f"{{{BAH_NAMESPACE}}}Prty").text == "HIGH"

    xml_str = header.to_xml()
    assert "SNDRBEBBXXX" in xml_str
    assert "BIZ-MSG-2026-9999" in xml_str


def test_bah_org_id_sender_and_receiver() -> None:
    """Verify non-BIC organisation identifiers are serialized in <OrgId>."""
    header = BusinessApplicationHeader(
        from_id="ORG-SENDER-123",
        to_id="ORG-RECEIVER-456",
        pssbl_dplct=False,
    )
    el = header.to_element()
    assert (
        el.find(f".//{{{BAH_NAMESPACE}}}Othr/{{{BAH_NAMESPACE}}}Id").text
        == "ORG-SENDER-123"
    )
    assert (
        el.find(
            f"{{{BAH_NAMESPACE}}}To//{{{BAH_NAMESPACE}}}Othr/{{{BAH_NAMESPACE}}}Id"
        ).text
        == "ORG-RECEIVER-456"
    )
    assert el.find(f"{{{BAH_NAMESPACE}}}PssblDplct").text == "false"


def test_bah_with_signature_element_and_string() -> None:
    """Verify BAH embeds XML signature both from element and string."""
    sig_raw = '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#"><SignatureValue>ABCD</SignatureValue></Signature>'
    header_str_sig = BusinessApplicationHeader(signature=sig_raw)
    el1 = header_str_sig.to_element()
    assert el1.find(f".//{{{BAH_NAMESPACE}}}Sgntr") is not None

    sig_el = et.Element("{http://www.w3.org/2000/09/xmldsig#}Signature")
    val = et.SubElement(
        sig_el, "{http://www.w3.org/2000/09/xmldsig#}SignatureValue"
    )
    val.text = "EFGH"
    header_el_sig = BusinessApplicationHeader(signature=sig_el)
    el2 = header_el_sig.to_element()
    assert el2.find(f".//{{{BAH_NAMESPACE}}}Sgntr") is not None


def test_extract_msg_def_idr() -> None:
    """Verify message definition extraction from XML string and ElementTree."""
    assert extract_msg_def_idr(SAMPLE_DOC_XML) == "pain.001.001.03"

    p008_xml = (
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"/>'
    )
    assert extract_msg_def_idr(p008_xml) == "pain.008.001.02"

    root_el = et.fromstring(p008_xml)
    assert extract_msg_def_idr(root_el) == "pain.008.001.02"

    no_ns_el = et.Element("Document")
    assert extract_msg_def_idr(no_ns_el) == "pain.001.001.03"

    plain_xml = "<Document></Document>"
    assert extract_msg_def_idr(plain_xml) == "pain.001.001.03"

    other_ns_el = et.Element("{urn:other:system}Doc")
    assert extract_msg_def_idr(other_ns_el) == "pain.001.001.03"


def test_envelop_iso20022_message_wrapped() -> None:
    """Verify standard head.003 wrapping with <Hdr> and <Pyld>."""
    header = BusinessApplicationHeader(
        from_bic="TESTBIC1XXX",
        to_bic="TESTBIC2XXX",
        biz_msg_idr="MSG-12345",
    )
    enveloped = envelop_iso20022_message(SAMPLE_DOC_XML, header, wrapped=True)

    assert enveloped.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert (
        f"{{{BIZDATA_NAMESPACE}}}BizData" in enveloped
        or "BizData" in enveloped
    )
    assert "TESTBIC1XXX" in enveloped
    assert "MSG-12345" in enveloped
    assert "CstmrCdtTrfInitn" in enveloped


def test_envelop_auto_infer_msg_def_idr() -> None:
    """Verify msg_def_idr is automatically inferred from document XML if omitted."""
    header = BusinessApplicationHeader()
    assert header.msg_def_idr is None
    enveloped = envelop_iso20022_message(SAMPLE_DOC_XML, header, wrapped=True)
    assert "pain.001.001.03" in enveloped


def test_envelop_iso20022_message_unwrapped_and_from_element() -> None:
    """Verify flat BizData enveloping without <Hdr>/<Pyld> wrappers."""
    header = BusinessApplicationHeader(from_bic="BANKAABBXXX")
    doc_el = et.fromstring(SAMPLE_DOC_XML)
    enveloped = envelop_iso20022_message(doc_el, header, wrapped=False)

    assert "BizData" in enveloped
    assert "BANKAABBXXX" in enveloped


def test_unpack_iso20022_message_roundtrip() -> None:
    """Verify unpacking recovers BAH header fields and underlying Document XML."""
    header = BusinessApplicationHeader(
        from_bic="SNDRBIC1XXX",
        to_bic="RCVRBIC2XXX",
        biz_msg_idr="UNPACK-001",
        msg_def_idr="pain.001.001.03",
        char_set="UTF-8",
        biz_svc="urn:epc:sepa",
        cre_dt="2026-09-26T20:15:00Z",
        cpy_dplct="DUPL",
        pssbl_dplct=True,
        prty="NORM",
    )
    enveloped = envelop_iso20022_message(SAMPLE_DOC_XML, header, wrapped=True)

    unpacked_hdr, unpacked_doc = unpack_iso20022_message(enveloped)
    assert unpacked_hdr is not None
    assert unpacked_hdr.from_bic == "SNDRBIC1XXX"
    assert unpacked_hdr.to_bic == "RCVRBIC2XXX"
    assert unpacked_hdr.biz_msg_idr == "UNPACK-001"
    assert unpacked_hdr.msg_def_idr == "pain.001.001.03"
    assert unpacked_hdr.char_set == "UTF-8"
    assert unpacked_hdr.biz_svc == "urn:epc:sepa"
    assert unpacked_hdr.cpy_dplct == "DUPL"
    assert unpacked_hdr.pssbl_dplct is True
    assert unpacked_hdr.prty == "NORM"
    assert "CstmrCdtTrfInitn" in unpacked_doc


def test_unpack_apphdr_without_msg_def_idr() -> None:
    """Verify unpacking when AppHdr has no MsgDefIdr element."""
    xml_content = (
        f'<BizData xmlns="{BIZDATA_NAMESPACE}">'
        f'<AppHdr xmlns="{BAH_NAMESPACE}">'
        f"<Fr><FIId><FinInstnId><BICFI>TESTBIC1XXX</BICFI></FinInstnId></FIId></Fr>"
        f"<To><FIId><FinInstnId><BICFI>TESTBIC2XXX</BICFI></FinInstnId></FIId></To>"
        f"<BizMsgIdr>MSG-TEST</BizMsgIdr>"
        f"<CreDt>2026-09-26T21:00:00Z</CreDt>"
        f"</AppHdr>"
        f'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">'
        f"<CstmrCdtTrfInitn/>"
        f"</Document>"
        f"</BizData>"
    )
    hdr, doc = unpack_iso20022_message(xml_content)
    assert hdr is not None
    assert hdr.msg_def_idr is None
    assert "CstmrCdtTrfInitn" in doc


def test_unpack_apphdr_empty_sgntr() -> None:
    """Verify unpacking AppHdr with empty Sgntr element."""
    xml_content = (
        f'<BizData xmlns="{BIZDATA_NAMESPACE}">'
        f'<AppHdr xmlns="{BAH_NAMESPACE}">'
        f"<Fr><FIId><FinInstnId><BICFI>TESTBIC1XXX</BICFI></FinInstnId></FIId></Fr>"
        f"<To><FIId><FinInstnId><BICFI>TESTBIC2XXX</BICFI></FinInstnId></FIId></To>"
        f"<BizMsgIdr>MSG-EMPTY-SIG</BizMsgIdr>"
        f"<MsgDefIdr>pain.001.001.03</MsgDefIdr>"
        f"<CreDt>2026-09-26T21:00:00Z</CreDt>"
        f"<Sgntr/>"
        f"</AppHdr>"
        f"</BizData>"
    )
    hdr, _ = unpack_iso20022_message(xml_content)
    assert hdr is not None
    assert hdr.signature is None


def test_unpack_non_enveloped_passthrough() -> None:
    """Verify raw ISO 20022 document passes through unpack untouched."""
    hdr, doc = unpack_iso20022_message(SAMPLE_DOC_XML)
    assert hdr is None
    assert doc == SAMPLE_DOC_XML

    hdr_b, doc_b = unpack_iso20022_message(SAMPLE_DOC_XML.encode("utf-8"))
    assert hdr_b is None
    assert doc_b == SAMPLE_DOC_XML


def test_unpack_no_document_in_envelope() -> None:
    """Verify handling when envelope has AppHdr but no Document element."""
    xml_no_doc = (
        f'<BizData xmlns="{BIZDATA_NAMESPACE}">'
        f'<AppHdr xmlns="{BAH_NAMESPACE}">'
        f"<Fr><FIId><FinInstnId><BICFI>TESTBIC1XXX</BICFI></FinInstnId></FIId></Fr>"
        f"<To><FIId><FinInstnId><BICFI>TESTBIC2XXX</BICFI></FinInstnId></FIId></To>"
        f"<BizMsgIdr>MSG-EMPTY</BizMsgIdr>"
        f"<MsgDefIdr>head.001.001.03</MsgDefIdr>"
        f"<CreDt>2026-09-26T21:00:00Z</CreDt>"
        f"</AppHdr>"
        f"</BizData>"
    )
    hdr, doc = unpack_iso20022_message(xml_no_doc)
    assert hdr is not None
    assert hdr.biz_msg_idr == "MSG-EMPTY"
    assert doc == xml_no_doc


def test_unpack_missing_apphdr_in_tagged_xml() -> None:
    """Verify handling when AppHdr text is in string but no AppHdr element exists."""
    bad_xml = "<BizData><!-- AppHdr mentioned here --><Document/></BizData>"
    hdr, doc = unpack_iso20022_message(bad_xml)
    assert hdr is None
    assert doc == bad_xml


def test_envelop_empty_msg_def_idr() -> None:
    """Verify enveloping when msg_def_idr is explicitly empty string."""
    header = BusinessApplicationHeader(msg_def_idr="")
    enveloped = envelop_iso20022_message(SAMPLE_DOC_XML, header)
    assert "<BizData" in enveloped


def test_unpack_non_namespaced_bic_and_extra_tag() -> None:
    """Verify unpacking BAH with non-namespaced BICFI and unknown tag."""
    xml_content = (
        "<BizData>"
        "<AppHdr>"
        "<Fr><FIId><FinInstnId><BICFI>TESTBIC1XXX</BICFI></FinInstnId></FIId></Fr>"
        "<To><FIId><FinInstnId><BICFI>TESTBIC2XXX</BICFI></FinInstnId></FIId></To>"
        "<BizMsgIdr>MSG-TEST-NO-NS</BizMsgIdr>"
        "<CustomTag>ignored</CustomTag>"
        "</AppHdr>"
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"/>'
        "</BizData>"
    )
    hdr, _ = unpack_iso20022_message(xml_content)
    assert hdr is not None
    assert hdr.from_bic == "TESTBIC1XXX"
    assert hdr.to_bic == "TESTBIC2XXX"


def test_unpack_org_ids_for_from_and_to() -> None:
    """Verify unpacking BAH when sender and receiver use OrgId instead of BICFI."""
    xml_content = (
        f'<BizData xmlns="{BIZDATA_NAMESPACE}">'
        f'<AppHdr xmlns="{BAH_NAMESPACE}">'
        f"<Fr><OrgId><Id>ORG-SNDR-999</Id></OrgId></Fr>"
        f"<To><OrgId><Id>ORG-RCVR-888</Id></OrgId></To>"
        f"<BizMsgIdr>MSG-ORG-IDS</BizMsgIdr>"
        f"</AppHdr>"
        f'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"/>'
        f"</BizData>"
    )
    hdr, _ = unpack_iso20022_message(xml_content)
    assert hdr is not None
    assert hdr.from_id == "ORG-SNDR-999"
    assert hdr.to_id == "ORG-RCVR-888"


def test_unpack_fr_to_without_bic_or_id() -> None:
    """Verify unpacking BAH when Fr and To contain neither BICFI nor Id elements."""
    xml_content = (
        f'<BizData xmlns="{BIZDATA_NAMESPACE}">'
        f'<AppHdr xmlns="{BAH_NAMESPACE}">'
        f"<Fr><Unknown/></Fr>"
        f"<To><Unknown/></To>"
        f"<BizMsgIdr>MSG-NO-ID</BizMsgIdr>"
        f"</AppHdr>"
        f'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"/>'
        f"</BizData>"
    )
    hdr, _ = unpack_iso20022_message(xml_content)
    assert hdr is not None
    assert hdr.from_bic is None
    assert hdr.from_id is None
    assert hdr.to_bic is None
    assert hdr.to_id is None
