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

"""Parser for ISO 20022 camt.053 bank statements."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

from pain001.exceptions import DataSourceError, SchemaValidationError
from pain001.security import validate_path
from pain001.xml.validate_via_xsd import validate_via_xsd


def parse_camt053_statement(
    xml_file_path: str,
    xsd_file_path: str | None = None,
    *,
    base_dir: str | Path | None = None,
) -> dict[str, object]:
    """Parse a camt.053 statement into a compact Python structure.

    ``base_dir`` names the directory the XML path must stay inside; by
    default the path guard allows the working directory, the temp
    directories and the package.
    """
    try:
        safe_xml_path = validate_path(
            xml_file_path, base_dir=base_dir, must_exist=True
        )
    except Exception as exc:
        raise DataSourceError(f"Invalid camt.053 XML path: {exc}") from exc

    if xsd_file_path:
        try:
            safe_xsd_path = validate_path(xsd_file_path, must_exist=True)
        except Exception as exc:
            raise DataSourceError(f"Invalid camt.053 XSD path: {exc}") from exc
        if not validate_via_xsd(safe_xml_path, safe_xsd_path):
            raise SchemaValidationError(
                f"camt.053 XML failed validation against {safe_xsd_path}"
            )

    try:
        root = defused_et.parse(safe_xml_path).getroot()
    except (ParseError, OSError) as exc:
        raise DataSourceError(f"Unable to parse camt.053 XML: {exc}") from exc
    if root is None:  # pragma: no cover - a parsed document always has a root
        raise DataSourceError("camt.053 XML document is empty")

    ns = _detect_namespace(root)
    statements = [
        _statement(statement, ns) for statement in root.findall(f".//{ns}Stmt")
    ]
    if not statements:
        raise DataSourceError("Input XML is not a camt.053 statement")
    # The first statement's fields stay at the top level for existing
    # callers; every statement is in "statements".
    return {**statements[0], "statements": statements}


def _statement(statement: Any, ns: str) -> dict[str, Any]:
    """Return one Stmt with its entries.

    Args:
        statement: The Stmt element.
        ns: The document namespace in ElementTree search form.

    Returns:
        The statement's identifiers, account, currency and entries.
    """
    return {
        "statement_id": _find_text(statement, ns, "Id"),
        "electronic_sequence_number": _find_text(
            statement, ns, "ElctrncSeqNb"
        ),
        "iban": _find_text(statement, ns, "Acct/Id/IBAN"),
        "currency": _find_text(statement, ns, "Acct/Ccy"),
        "entries": [
            _entry(entry, ns) for entry in statement.findall(f"{ns}Ntry")
        ],
    }


def _entry(entry: Any, ns: str) -> dict[str, Any]:
    """Return one Ntry as a flat record.

    ``Sts`` is text up to camt.053.001.07 and ``Sts/Cd`` from .08 on;
    both are read. Every ``TxDtls/Refs/EndToEndId`` is listed so a
    booking can be matched to the payments it settles.

    Args:
        entry: The Ntry element.
        ns: The document namespace in ElementTree search form.

    Returns:
        The entry's amount, dates, status, references and remittance.
    """
    amount = entry.find(f"{ns}Amt")
    return {
        "credit_debit_indicator": _find_text(entry, ns, "CdtDbtInd"),
        "status": _find_text(entry, ns, "Sts")
        or _find_text(entry, ns, "Sts/Cd"),
        "booking_date": _find_text(entry, ns, "BookgDt/Dt"),
        "value_date": _find_text(entry, ns, "ValDt/Dt"),
        "amount": (amount.text or "").strip()
        if amount is not None and amount.text
        else "",
        "currency": amount.attrib.get("Ccy", "") if amount is not None else "",
        "entry_reference": _find_text(entry, ns, "AcctSvcrRef"),
        "remittance_information": _find_text(
            entry, ns, "NtryDtls/TxDtls/RmtInf/Ustrd"
        ),
        "end_to_end_ids": [
            (ref.text or "").strip()
            for ref in entry.findall(
                f"{ns}NtryDtls/{ns}TxDtls/{ns}Refs/{ns}EndToEndId"
            )
            if ref.text
        ],
    }


def _detect_namespace(root: Any) -> str:
    """Return the element namespace in ElementTree search format."""
    tag = str(root.tag)
    if tag.startswith("{"):
        return tag.split("}", maxsplit=1)[0] + "}"
    return ""


def _find_text(parent: Any, ns: str, path: str) -> str:
    """Read nested text using slash-separated relative paths."""
    current: Any = parent
    for part in path.split("/"):
        current = current.find(f"{ns}{part}")
        if current is None:
            return ""
    return (current.text or "").strip()
