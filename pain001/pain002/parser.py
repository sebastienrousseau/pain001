# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parser for ISO 20022 pain.002 payment status reports."""

from __future__ import annotations

from typing import Any

from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

from pain001.exceptions import DataSourceError, SchemaValidationError
from pain001.security import validate_path
from pain001.xml.validate_via_xsd import validate_via_xsd


def parse_pain002_report(
    xml_file_path: str, xsd_file_path: str | None = None
) -> dict[str, object]:
    """Parse a pain.002 payment status report into structured data."""
    try:
        safe_xml_path = validate_path(xml_file_path, must_exist=True)
    except Exception as exc:
        raise DataSourceError(f"Invalid pain.002 XML path: {exc}") from exc

    if xsd_file_path:
        try:
            safe_xsd_path = validate_path(xsd_file_path, must_exist=True)
        except Exception as exc:
            raise DataSourceError(f"Invalid pain.002 XSD path: {exc}") from exc
        if not validate_via_xsd(safe_xml_path, safe_xsd_path):
            raise SchemaValidationError(
                f"pain.002 XML failed validation against {safe_xsd_path}"
            )

    try:
        root = defused_et.parse(safe_xml_path).getroot()
    except (ParseError, OSError) as exc:
        raise DataSourceError(f"Unable to parse pain.002 XML: {exc}") from exc
    if root is None:  # pragma: no cover
        raise DataSourceError(
            "pain.002 XML document is empty"
        )  # pragma: no cover

    ns = _detect_namespace(root)
    report = root.find(f".//{ns}CstmrPmtStsRpt")
    if report is None:
        raise DataSourceError(
            "Input XML is not a pain.002 payment status report"
        )

    statuses: list[dict[str, str]] = []
    for payment_info in report.findall(f"{ns}OrgnlPmtInfAndSts"):
        status_record = {
            "original_payment_information_id": _find_text(
                payment_info, ns, "OrgnlPmtInfId"
            ),
            "payment_information_status": _find_text(
                payment_info, ns, "PmtInfSts"
            ),
        }
        tx_status = payment_info.find(f"{ns}TxInfAndSts")
        if tx_status is not None:  # pragma: no cover
            status_record["original_end_to_end_id"] = _find_text(
                tx_status, ns, "OrgnlEndToEndId"
            )
            status_record["transaction_status"] = _find_text(
                tx_status, ns, "TxSts"
            )
            status_record["status_reason"] = _find_text(
                tx_status, ns, "StsRsnInf/Rsn/Cd"
            )
        statuses.append(status_record)

    return {
        "message_id": _find_text(report, ns, "GrpHdr/MsgId"),
        "creation_datetime": _find_text(report, ns, "GrpHdr/CreDtTm"),
        "original_message_id": _find_text(
            report, ns, "OrgnlGrpInfAndSts/OrgnlMsgId"
        ),
        "original_message_name_id": _find_text(
            report, ns, "OrgnlGrpInfAndSts/OrgnlMsgNmId"
        ),
        "group_status": _find_text(report, ns, "OrgnlGrpInfAndSts/GrpSts"),
        "payment_statuses": statuses,
    }


def _detect_namespace(root: Any) -> str:
    """Return the element namespace in ElementTree search format."""
    tag = str(root.tag)
    if tag.startswith("{"):
        return tag.split("}", maxsplit=1)[0] + "}"
    return ""


def _find_text(parent: Any, ns: str, path: str) -> str:
    """Read nested text using slash-separated relative paths."""
    current: Any | None = parent
    for part in path.split("/"):
        current = current.find(f"{ns}{part}") if current is not None else None
        if current is None:  # pragma: no cover
            return ""  # pragma: no cover
    if current is None:  # pragma: no cover
        return ""  # pragma: no cover
    return (current.text or "").strip()
