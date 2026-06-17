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

"""Builder for ISO 20022 pain.002 payment status reports.

The complement to :func:`pain001.pain002.parse_pain002_report`: given the
status a bank (or a test harness simulating one) wants to report, produce a
well-formed pain.002 XML document. Generation uses the standard library's
ElementTree (output is fully under our control); the result round-trips
cleanly back through the parser.
"""

from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET  # nosec B405 - generation only

#: Status codes defined by ISO 20022 for group/payment/transaction status.
VALID_STATUS_CODES = frozenset(
    {"ACCP", "ACSC", "ACSP", "ACTC", "ACWC", "PART", "PDNG", "RCVD", "RJCT"}
)


def _ns(version: str) -> str:
    """Return the ISO 20022 namespace URI for a pain.002 version.

    Args:
        version: Message version, e.g. ``pain.002.001.03``.

    Returns:
        The namespace URI.
    """
    return f"urn:iso:std:iso:20022:tech:xsd:{version}"


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    """Append a child element, optionally with text.

    Args:
        parent: The parent element.
        tag: The (already namespaced) child tag.
        text: Optional text content.

    Returns:
        The created child element.
    """
    child = ET.SubElement(parent, tag)
    if text is not None:
        child.text = text
    return child


def build_pain002_report(
    message_id: str,
    original_message_id: str,
    group_status: str,
    payment_statuses: list[dict[str, Any]],
    *,
    original_message_name_id: str = "pain.001.001.03",
    creation_datetime: str | None = None,
    version: str = "pain.002.001.03",
) -> str:
    """Build a pain.002 payment status report as an XML string.

    Args:
        message_id: Identifier for this status report (``GrpHdr/MsgId``).
        original_message_id: The id of the pain.001 message being reported
            on (``OrgnlGrpInfAndSts/OrgnlMsgId``).
        group_status: Group-level status code (e.g. ``ACCP``, ``RJCT``).
        payment_statuses: One dict per original payment information block.
            Recognised keys: ``original_payment_information_id`` (required),
            ``payment_information_status`` (required), and the optional
            transaction triplet ``original_end_to_end_id``,
            ``transaction_status``, ``status_reason``.
        original_message_name_id: Name id of the original message
            (default ``pain.001.001.03``).
        creation_datetime: ISO-8601 creation timestamp; defaults to now (UTC).
        version: pain.002 message version (drives the namespace).

    Returns:
        The pain.002 report as a UTF-8 XML string (with declaration).

    Raises:
        ValueError: If ``group_status`` or any row status is not a known
            ISO 20022 status code, or a required row key is missing.
    """
    if group_status not in VALID_STATUS_CODES:
        raise ValueError(f"Invalid group status code: {group_status!r}")

    ns = _ns(version)
    ET.register_namespace("", ns)

    def q(tag: str) -> str:
        """Namespace-qualify a tag.

        Args:
            tag: The local tag name.

        Returns:
            The Clark-notation qualified tag.
        """
        return f"{{{ns}}}{tag}"

    when = creation_datetime or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    document = ET.Element(q("Document"))
    report = _sub(document, q("CstmrPmtStsRpt"))

    grp_hdr = _sub(report, q("GrpHdr"))
    _sub(grp_hdr, q("MsgId"), message_id)
    _sub(grp_hdr, q("CreDtTm"), when)

    orig = _sub(report, q("OrgnlGrpInfAndSts"))
    _sub(orig, q("OrgnlMsgId"), original_message_id)
    _sub(orig, q("OrgnlMsgNmId"), original_message_name_id)
    _sub(orig, q("GrpSts"), group_status)

    for row in payment_statuses:
        _append_payment_status(report, q, row)

    xml_bytes: bytes = ET.tostring(
        document, encoding="utf-8", xml_declaration=True
    )
    return xml_bytes.decode("utf-8")


def _append_payment_status(
    report: ET.Element, q: Any, row: dict[str, Any]
) -> None:
    """Append one OrgnlPmtInfAndSts block to the report.

    Args:
        report: The ``CstmrPmtStsRpt`` element.
        q: A tag-qualifier callable.
        row: The payment-status row (see :func:`build_pain002_report`).

    Raises:
        ValueError: If a required key is missing or a status code is invalid.
    """
    try:
        pmt_inf_id = str(row["original_payment_information_id"])
        pmt_status = str(row["payment_information_status"])
    except KeyError as exc:
        raise ValueError(f"payment status row missing key: {exc}") from exc
    if pmt_status not in VALID_STATUS_CODES:
        raise ValueError(f"Invalid payment status code: {pmt_status!r}")

    block = _sub(report, q("OrgnlPmtInfAndSts"))
    _sub(block, q("OrgnlPmtInfId"), pmt_inf_id)
    _sub(block, q("PmtInfSts"), pmt_status)

    if "transaction_status" in row:
        tx_status = str(row["transaction_status"])
        if tx_status not in VALID_STATUS_CODES:
            raise ValueError(f"Invalid transaction status: {tx_status!r}")
        tx = _sub(block, q("TxInfAndSts"))
        _sub(
            tx,
            q("OrgnlEndToEndId"),
            str(row.get("original_end_to_end_id", "")),
        )
        _sub(tx, q("TxSts"), tx_status)
        reason = row.get("status_reason")
        if reason:
            rsn_inf = _sub(tx, q("StsRsnInf"))
            rsn = _sub(rsn_inf, q("Rsn"))
            _sub(rsn, q("Cd"), str(reason))
