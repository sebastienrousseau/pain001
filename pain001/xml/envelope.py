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

"""ISO 20022 Business Application Header (head.001.001.03) and Envelope."""

from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as et  # nosec B405
from dataclasses import dataclass
from datetime import datetime, timezone

import defusedxml.ElementTree as defused_et

BAH_NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:head.001.001.03"
BIZDATA_NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:head.003.001.01"
XML_DSIG_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"


@dataclass
class BusinessApplicationHeader:
    """ISO 20022 Business Application Header (BAH head.001.001.03) model.

    Attributes:
        from_bic: Sender Financial Institution BIC (BICFI).
        from_id: Sender Organisation Identifier if not a BIC.
        to_bic: Receiver Financial Institution BIC (BICFI).
        to_id: Receiver Organisation Identifier if not a BIC.
        biz_msg_idr: Business Message Identifier (max 35 chars).
        msg_def_idr: Message Definition Identifier (e.g. pain.001.001.03).
        cre_dt: Message Creation Date Time in ISO format (UTC).
        char_set: Optional character set encoding string.
        biz_svc: Optional business service name.
        cpy_dplct: Optional copy / duplicate indicator (CODU, COPY, DUPL).
        pssbl_dplct: Optional possible duplicate flag (True/False).
        prty: Optional priority code (e.g. HIGH, NORM).
        signature: Optional XML-DSig signature element or raw XML string.
    """

    from_bic: str | None = None
    from_id: str | None = None
    to_bic: str | None = None
    to_id: str | None = None
    biz_msg_idr: str | None = None
    msg_def_idr: str | None = None
    cre_dt: str | None = None
    char_set: str | None = None
    biz_svc: str | None = None
    cpy_dplct: str | None = None
    pssbl_dplct: bool | None = None
    prty: str | None = None
    signature: str | et.Element | None = None

    def to_element(self) -> et.Element:
        """Construct the XML ElementTree representation of head.001.001.03.

        Returns:
            An ElementTree.Element representing <AppHdr>.
        """
        app_hdr = et.Element(f"{{{BAH_NAMESPACE}}}AppHdr")

        if self.char_set:
            char_set_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}CharSet")
            char_set_el.text = self.char_set

        # <Fr>
        fr_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}Fr")
        if self.from_bic:
            fi_id = et.SubElement(fr_el, f"{{{BAH_NAMESPACE}}}FIId")
            fin_instn = et.SubElement(fi_id, f"{{{BAH_NAMESPACE}}}FinInstnId")
            bicfi = et.SubElement(fin_instn, f"{{{BAH_NAMESPACE}}}BICFI")
            bicfi.text = self.from_bic
        elif self.from_id:
            org_id = et.SubElement(fr_el, f"{{{BAH_NAMESPACE}}}OrgId")
            id_el = et.SubElement(org_id, f"{{{BAH_NAMESPACE}}}Id")
            org_sub = et.SubElement(id_el, f"{{{BAH_NAMESPACE}}}OrgId")
            othr = et.SubElement(org_sub, f"{{{BAH_NAMESPACE}}}Othr")
            other_id = et.SubElement(othr, f"{{{BAH_NAMESPACE}}}Id")
            other_id.text = self.from_id
        else:
            fi_id = et.SubElement(fr_el, f"{{{BAH_NAMESPACE}}}FIId")
            fin_instn = et.SubElement(fi_id, f"{{{BAH_NAMESPACE}}}FinInstnId")
            bicfi = et.SubElement(fin_instn, f"{{{BAH_NAMESPACE}}}BICFI")
            bicfi.text = "NOTPROVIDED"

        # <To>
        to_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}To")
        if self.to_bic:
            fi_id = et.SubElement(to_el, f"{{{BAH_NAMESPACE}}}FIId")
            fin_instn = et.SubElement(fi_id, f"{{{BAH_NAMESPACE}}}FinInstnId")
            bicfi = et.SubElement(fin_instn, f"{{{BAH_NAMESPACE}}}BICFI")
            bicfi.text = self.to_bic
        elif self.to_id:
            org_id = et.SubElement(to_el, f"{{{BAH_NAMESPACE}}}OrgId")
            id_el = et.SubElement(org_id, f"{{{BAH_NAMESPACE}}}Id")
            org_sub = et.SubElement(id_el, f"{{{BAH_NAMESPACE}}}OrgId")
            othr = et.SubElement(org_sub, f"{{{BAH_NAMESPACE}}}Othr")
            other_id = et.SubElement(othr, f"{{{BAH_NAMESPACE}}}Id")
            other_id.text = self.to_id
        else:
            fi_id = et.SubElement(to_el, f"{{{BAH_NAMESPACE}}}FIId")
            fin_instn = et.SubElement(fi_id, f"{{{BAH_NAMESPACE}}}FinInstnId")
            bicfi = et.SubElement(fin_instn, f"{{{BAH_NAMESPACE}}}BICFI")
            bicfi.text = "NOTPROVIDED"

        # <BizMsgIdr>
        biz_msg_idr_val = (
            self.biz_msg_idr or f"MSG-{uuid.uuid4().hex[:16].upper()}"
        )
        biz_msg_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}BizMsgIdr")
        biz_msg_el.text = biz_msg_idr_val

        # <MsgDefIdr>
        msg_def_idr_val = self.msg_def_idr or "pain.001.001.03"
        msg_def_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}MsgDefIdr")
        msg_def_el.text = msg_def_idr_val

        if self.biz_svc:
            biz_svc_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}BizSvc")
            biz_svc_el.text = self.biz_svc

        # <CreDt>
        cre_dt_val = self.cre_dt or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        cre_dt_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}CreDt")
        cre_dt_el.text = cre_dt_val

        if self.cpy_dplct:
            cpy_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}CpyDplct")
            cpy_el.text = self.cpy_dplct

        if self.pssbl_dplct is not None:
            pssbl_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}PssblDplct")
            pssbl_el.text = "true" if self.pssbl_dplct else "false"

        if self.prty:
            prty_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}Prty")
            prty_el.text = self.prty

        # <Sgntr>
        if self.signature is not None:
            sgntr_el = et.SubElement(app_hdr, f"{{{BAH_NAMESPACE}}}Sgntr")
            if isinstance(self.signature, str):
                sig_parsed = defused_et.fromstring(self.signature)
                sgntr_el.append(sig_parsed)
            else:
                sgntr_el.append(self.signature)

        return app_hdr

    def to_xml(self) -> str:
        """Serialize the BAH to an XML string.

        Returns:
            The serialized <AppHdr> XML string.
        """
        element = self.to_element()
        return et.tostring(element, encoding="unicode")


def extract_msg_def_idr(document_xml: str | et.Element) -> str:
    """Extract or infer the ISO 20022 message definition identifier.

    Args:
        document_xml: The raw XML string or root Element.

    Returns:
        The detected identifier such as 'pain.001.001.03'.
    """
    if isinstance(document_xml, et.Element):
        tag = document_xml.tag
        if tag.startswith("{"):
            ns = tag[1 : tag.find("}")]
            match = re.search(r"urn:iso:std:iso:20022:tech:xsd:([\w.]+)", ns)
            if match:
                return match.group(1)
        return "pain.001.001.03"

    match = re.search(
        r'xmlns(?::\w+)?=["\']urn:iso:std:iso:20022:tech:xsd:([\w.]+)["\']',
        document_xml,
    )
    if match:
        return match.group(1)
    return "pain.001.001.03"


def envelop_iso20022_message(
    document_xml: str | et.Element,
    header: BusinessApplicationHeader,
    wrapped: bool = True,
) -> str:
    """Envelop an ISO 20022 payment document inside a head.003 BizData envelope.

    Args:
        document_xml: The ISO 20022 document XML string or Element.
        header: The BusinessApplicationHeader metadata instance.
        wrapped: If True, wrap AppHdr in <Hdr> and Document in <Pyld>
            per ISO 20022 head.003 standard schema. If False, place AppHdr
            and Document directly under <BizData>.

    Returns:
        The complete enveloped ISO 20022 XML document with XML declaration.
    """
    if header.msg_def_idr is None:
        header.msg_def_idr = extract_msg_def_idr(document_xml)

    if isinstance(document_xml, str):
        doc_root = defused_et.fromstring(document_xml)
    else:
        doc_root = document_xml

    et.register_namespace("", BIZDATA_NAMESPACE)
    et.register_namespace("head", BAH_NAMESPACE)
    if header.msg_def_idr:
        et.register_namespace(
            "doc", f"urn:iso:std:iso:20022:tech:xsd:{header.msg_def_idr}"
        )
    et.register_namespace("ds", XML_DSIG_NAMESPACE)

    biz_data = et.Element(f"{{{BIZDATA_NAMESPACE}}}BizData")
    app_hdr_el = header.to_element()

    if wrapped:
        hdr_el = et.SubElement(biz_data, f"{{{BIZDATA_NAMESPACE}}}Hdr")
        hdr_el.append(app_hdr_el)
        pyld_el = et.SubElement(biz_data, f"{{{BIZDATA_NAMESPACE}}}Pyld")
        pyld_el.append(doc_root)
    else:
        biz_data.append(app_hdr_el)
        biz_data.append(doc_root)

    xml_body = et.tostring(biz_data, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}'


def unpack_iso20022_message(
    xml_content: str | bytes,
) -> tuple[BusinessApplicationHeader | None, str]:
    """Unpack an enveloped ISO 20022 message, extracting BAH and Document.

    Args:
        xml_content: The XML payload string or bytes.

    Returns:
        A tuple of (BusinessApplicationHeader, document_xml_str). If the input
        is not enveloped inside BizData or AppHdr, returns (None, xml_content).
    """
    if isinstance(xml_content, bytes):
        raw_str = xml_content.decode("utf-8")
    else:
        raw_str = xml_content

    if "AppHdr" not in raw_str:
        return None, raw_str

    root = defused_et.fromstring(raw_str)

    # Search for AppHdr element
    app_hdr_el = None
    for el in root.iter():
        if el.tag.endswith("AppHdr"):
            app_hdr_el = el
            break

    if app_hdr_el is None:
        return None, raw_str

    header = _parse_app_hdr_element(app_hdr_el)

    # Search for Document element
    doc_el = None
    for el in root.iter():
        if el.tag.endswith("Document"):
            doc_el = el
            break

    if doc_el is not None:
        if header.msg_def_idr:
            et.register_namespace(
                "", f"urn:iso:std:iso:20022:tech:xsd:{header.msg_def_idr}"
            )
        doc_xml = et.tostring(doc_el, encoding="unicode")
        doc_xml_str = f'<?xml version="1.0" encoding="UTF-8"?>\n{doc_xml}'
    else:
        doc_xml_str = raw_str

    return header, doc_xml_str


def _parse_app_hdr_element(
    app_hdr_el: et.Element,
) -> BusinessApplicationHeader:
    """Parse an <AppHdr> element into a BusinessApplicationHeader instance.

    Args:
        app_hdr_el: The XML element for AppHdr.

    Returns:
        A parsed BusinessApplicationHeader object.
    """
    char_set: str | None = None
    from_bic: str | None = None
    from_id: str | None = None
    to_bic: str | None = None
    to_id: str | None = None
    biz_msg_idr: str | None = None
    msg_def_idr: str | None = None
    biz_svc: str | None = None
    cre_dt: str | None = None
    cpy_dplct: str | None = None
    pssbl_dplct: bool | None = None
    prty: str | None = None
    signature: str | None = None

    for child in app_hdr_el:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "CharSet":
            char_set = child.text
        elif tag == "Fr":
            bic_el = child.find(f".//{{{BAH_NAMESPACE}}}BICFI")
            if bic_el is None:
                bic_el = child.find(".//BICFI")
            if bic_el is not None and bic_el.text:
                from_bic = bic_el.text
            else:
                for cand in child.iter():
                    if cand.tag.endswith("Id") and cand.text:
                        from_id = cand.text
                        break
        elif tag == "To":
            bic_el = child.find(f".//{{{BAH_NAMESPACE}}}BICFI")
            if bic_el is None:
                bic_el = child.find(".//BICFI")
            if bic_el is not None and bic_el.text:
                to_bic = bic_el.text
            else:
                for cand in child.iter():
                    if cand.tag.endswith("Id") and cand.text:
                        to_id = cand.text
                        break
        elif tag == "BizMsgIdr":
            biz_msg_idr = child.text
        elif tag == "MsgDefIdr":
            msg_def_idr = child.text
        elif tag == "BizSvc":
            biz_svc = child.text
        elif tag == "CreDt":
            cre_dt = child.text
        elif tag == "CpyDplct":
            cpy_dplct = child.text
        elif tag == "PssblDplct":
            pssbl_dplct = child.text == "true"
        elif tag == "Prty":
            prty = child.text
        elif tag == "Sgntr":
            signature = (
                et.tostring(child[0], encoding="unicode")
                if len(child) > 0
                else None
            )

    return BusinessApplicationHeader(
        from_bic=from_bic,
        from_id=from_id,
        to_bic=to_bic,
        to_id=to_id,
        biz_msg_idr=biz_msg_idr,
        msg_def_idr=msg_def_idr,
        cre_dt=cre_dt,
        char_set=char_set,
        biz_svc=biz_svc,
        cpy_dplct=cpy_dplct,
        pssbl_dplct=pssbl_dplct,
        prty=prty,
        signature=signature,
    )
