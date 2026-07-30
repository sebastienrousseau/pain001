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

"""Builder for ISO 20022 camt.053 bank-to-customer statements.

The complement to :func:`pain001.camt053.parse_camt053_statement`: build a
well-formed camt.053 statement from structured data — useful for simulating
a bank's end-of-day statement in tests. Output round-trips cleanly back
through the parser.
"""

from typing import Any
from xml.etree import ElementTree as ET  # nosec B405 - generation only

#: Recognised credit/debit indicators and entry statuses (ISO 20022).
VALID_CDT_DBT = frozenset({"CRDT", "DBIT"})
VALID_ENTRY_STATUS = frozenset({"BOOK", "PDNG", "INFO"})


def build_camt053_statement(
    statement_id: str,
    iban: str,
    currency: str,
    entries: list[dict[str, Any]],
    *,
    electronic_sequence_number: str = "1",
    version: str = "camt.053.001.02",
) -> str:
    """Build a camt.053 bank-to-customer statement as an XML string.

    Args:
        statement_id: Statement identifier (``Stmt/Id``).
        iban: Account IBAN (``Stmt/Acct/Id/IBAN``).
        currency: Account currency (``Stmt/Acct/Ccy``, ISO 4217).
        entries: One dict per booked entry. Recognised keys:
            ``amount`` (required), ``credit_debit_indicator`` (CRDT/DBIT,
            required), ``status`` (BOOK/PDNG/INFO, default BOOK),
            ``booking_date``, ``value_date``, ``entry_reference``,
            ``remittance_information``, and an optional per-entry
            ``currency`` (defaults to the account currency). A ``ValueError``
            is raised for an entry missing ``amount`` or carrying an invalid
            credit/debit indicator or status code.
        electronic_sequence_number: Statement sequence number.
        version: camt.053 message version (drives the namespace).

    Returns:
        The statement as a UTF-8 XML string (with declaration).
    """
    ns = f"urn:iso:std:iso:20022:tech:xsd:{version}"
    ET.register_namespace("", ns)

    def q(tag: str) -> str:
        """Namespace-qualify a tag.

        Args:
            tag: The local tag name.

        Returns:
            The Clark-notation qualified tag.
        """
        return f"{{{ns}}}{tag}"

    document = ET.Element(q("Document"))
    group = ET.SubElement(document, q("BkToCstmrStmt"))
    statement = ET.SubElement(group, q("Stmt"))
    ET.SubElement(statement, q("Id")).text = statement_id
    ET.SubElement(
        statement, q("ElctrncSeqNb")
    ).text = electronic_sequence_number

    account = ET.SubElement(statement, q("Acct"))
    acct_id = ET.SubElement(account, q("Id"))
    ET.SubElement(acct_id, q("IBAN")).text = iban
    ET.SubElement(account, q("Ccy")).text = currency

    for entry in entries:
        _append_entry(statement, q, entry, currency)

    xml_bytes: bytes = ET.tostring(
        document, encoding="utf-8", xml_declaration=True
    )
    return xml_bytes.decode("utf-8")


def _append_entry(
    statement: ET.Element, q: Any, entry: dict[str, Any], default_ccy: str
) -> None:
    """Append one ``Ntry`` block to the statement.

    Args:
        statement: The ``Stmt`` element.
        q: A tag-qualifier callable.
        entry: The entry row (see :func:`build_camt053_statement`).
        default_ccy: Account currency used when the entry omits its own.

    Raises:
        ValueError: If ``amount`` is missing or a code is invalid.
    """
    if "amount" not in entry:
        raise ValueError("camt.053 entry missing required key: 'amount'")
    cdt_dbt = str(entry.get("credit_debit_indicator", ""))
    if cdt_dbt not in VALID_CDT_DBT:
        raise ValueError(f"Invalid credit/debit indicator: {cdt_dbt!r}")
    status = str(entry.get("status", "BOOK"))
    if status not in VALID_ENTRY_STATUS:
        raise ValueError(f"Invalid entry status: {status!r}")

    ntry = ET.SubElement(statement, q("Ntry"))
    amount = ET.SubElement(ntry, q("Amt"))
    amount.set("Ccy", str(entry.get("currency") or default_ccy))
    amount.text = str(entry["amount"])
    ET.SubElement(ntry, q("CdtDbtInd")).text = cdt_dbt
    ET.SubElement(ntry, q("Sts")).text = status

    if entry.get("booking_date"):
        ET.SubElement(ET.SubElement(ntry, q("BookgDt")), q("Dt")).text = str(
            entry["booking_date"]
        )
    if entry.get("value_date"):
        ET.SubElement(ET.SubElement(ntry, q("ValDt")), q("Dt")).text = str(
            entry["value_date"]
        )
    if entry.get("entry_reference"):
        ET.SubElement(ntry, q("AcctSvcrRef")).text = str(
            entry["entry_reference"]
        )
    if entry.get("remittance_information"):
        ntry_dtls = ET.SubElement(ntry, q("NtryDtls"))
        tx_dtls = ET.SubElement(ntry_dtls, q("TxDtls"))
        rmt_inf = ET.SubElement(tx_dtls, q("RmtInf"))
        ET.SubElement(rmt_inf, q("Ustrd")).text = str(
            entry["remittance_information"]
        )
