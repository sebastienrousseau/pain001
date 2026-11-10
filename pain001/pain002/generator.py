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

"""Builder for ISO 20022 pain.002 payment status reports.

The complement to :func:`pain001.pain002.parse_pain002_report`: given the
status a bank (or a test harness simulating one) wants to report, produce a
well-formed pain.002 XML document. Generation uses the standard library's
ElementTree (output is fully under our control); the result round-trips
cleanly back through the parser.
"""

from collections.abc import Callable
from datetime import UTC, datetime
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
            ``payment_information_status`` (required), and either
            ``transactions``, a list of dicts each with
            ``transaction_status`` (required), ``original_end_to_end_id``
            and ``status_reason``, or that triplet directly on the row for
            a block with a single transaction.
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
    q = _qualifier(ns)
    when = creation_datetime or datetime.now(UTC).isoformat(timespec="seconds")

    document = ET.Element(q("Document"))
    report = _sub(document, q("CstmrPmtStsRpt"))
    _append_group(
        report,
        q,
        (message_id, when),
        (original_message_id, original_message_name_id, group_status),
    )
    for row in payment_statuses:
        _append_payment_status(report, q, row)

    xml_bytes: bytes = ET.tostring(
        document, encoding="utf-8", xml_declaration=True
    )
    return xml_bytes.decode("utf-8")


def _qualifier(ns: str) -> Callable[[str], str]:
    """A function that namespace-qualifies a tag in ``ns``.

    Args:
        ns: The message namespace URI.

    Returns:
        A callable turning a local tag name into Clark notation.
    """

    def q(tag: str) -> str:
        """Namespace-qualify a tag.

        Args:
            tag: The local tag name.

        Returns:
            The Clark-notation qualified tag.
        """
        return f"{{{ns}}}{tag}"

    return q


def _append_group(
    report: ET.Element,
    q: Callable[[str], str],
    header: tuple[str, str],
    original: tuple[str, str, str],
) -> None:
    """Append ``GrpHdr`` and ``OrgnlGrpInfAndSts`` to the report.

    Args:
        report: The ``CstmrPmtStsRpt`` element.
        q: A tag-qualifier callable.
        header: This report's message id and creation timestamp.
        original: The original message id, its name id and the group
            status.
    """
    grp_hdr = _sub(report, q("GrpHdr"))
    _sub(grp_hdr, q("MsgId"), header[0])
    _sub(grp_hdr, q("CreDtTm"), header[1])
    orig = _sub(report, q("OrgnlGrpInfAndSts"))
    for tag, text in zip(
        ("OrgnlMsgId", "OrgnlMsgNmId", "GrpSts"), original, strict=True
    ):
        _sub(orig, q(tag), text)


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

    for tx in _transactions_of(row):
        _append_transaction(block, q, tx)


_TX_KEYS = ("original_end_to_end_id", "transaction_status", "status_reason")


def _transactions_of(row: dict[str, Any]) -> list[dict[str, Any]]:
    """The transactions a payment-status row reports.

    A row may carry the flat transaction keys beside a ``transactions``
    list, as :func:`parse_pain002_report` returns it (the first
    transaction's keys repeated on the block); that is accepted when the
    flat keys agree with the first listed transaction.

    Args:
        row: The payment-status row (see :func:`build_pain002_report`).

    Returns:
        Its ``transactions`` list, the flat triplet as a one-item list,
        or an empty list when it reports none.

    Raises:
        ValueError: If ``transactions`` is not a list of dicts, a listed
            transaction has no ``transaction_status``, or the flat keys
            disagree with the first listed transaction.
    """
    if "transactions" not in row:
        return [row] if "transaction_status" in row else []
    transactions = _listed_transactions(row["transactions"])
    flat = {key: row[key] for key in _TX_KEYS if key in row}
    if flat and not _agrees(flat, transactions):
        raise ValueError(
            "payment status row: flat transaction keys disagree with "
            "transactions[0]"
        )
    return transactions


def _listed_transactions(value: Any) -> list[dict[str, Any]]:
    """Check that ``value`` is a list of transaction dicts with a status.

    Args:
        value: A row's ``transactions`` entry.

    Returns:
        The same list.

    Raises:
        ValueError: If it is not a list of dicts, or an entry has no
            ``transaction_status``.
    """
    if not isinstance(value, list) or not all(
        isinstance(tx, dict) for tx in value
    ):
        raise ValueError(
            "payment status row: transactions must be a list of dicts"
        )
    if any("transaction_status" not in tx for tx in value):
        raise ValueError(
            "listed transaction missing key: 'transaction_status'"
        )
    return value


def _agrees(flat: dict[str, Any], transactions: list[dict[str, Any]]) -> bool:
    """Whether the flat keys repeat the first listed transaction's values.

    Args:
        flat: The transaction keys found directly on the row.
        transactions: The row's listed transactions.

    Returns:
        ``True`` when there is a first transaction and every flat key
        has its value there.
    """
    return bool(transactions) and all(
        str(transactions[0].get(key, "")) == str(value)
        for key, value in flat.items()
    )


def _append_transaction(
    block: ET.Element, q: Callable[[str], str], tx: dict[str, Any]
) -> None:
    """Append one TxInfAndSts to a payment block.

    Args:
        block: The ``OrgnlPmtInfAndSts`` element.
        q: A tag-qualifier callable.
        tx: ``transaction_status``, and optionally
            ``original_end_to_end_id`` and ``status_reason``.

    Raises:
        ValueError: If the transaction status code is invalid.
    """
    tx_status = str(tx["transaction_status"])
    if tx_status not in VALID_STATUS_CODES:
        raise ValueError(f"Invalid transaction status: {tx_status!r}")
    element = _sub(block, q("TxInfAndSts"))
    _sub(
        element,
        q("OrgnlEndToEndId"),
        str(tx.get("original_end_to_end_id", "")),
    )
    _sub(element, q("TxSts"), tx_status)
    reason = tx.get("status_reason")
    if reason:
        rsn_inf = _sub(element, q("StsRsnInf"))
        rsn = _sub(rsn_inf, q("Rsn"))
        _sub(rsn, q("Cd"), str(reason))
