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

"""Parser for ISO 20022 pain.002 payment status reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

from pain001.exceptions import DataSourceError, SchemaValidationError
from pain001.security import validate_path
from pain001.xml.validate_via_xsd import validate_via_xsd

#: Bundled ISO schemas for validating a bank's pain.002 response.
#: The parser itself is namespace-agnostic, so a bank may send any
#: version; only these can be validated without supplying a path.
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def bundled_schema_versions() -> list[str]:
    """Return the pain.002 versions this package can validate."""
    return sorted(p.stem for p in SCHEMA_DIR.glob("pain.002.001.*.xsd"))


def schema_for_namespace(namespace: str) -> Path | None:
    """Map a document namespace to a bundled schema, if one exists.

    ``namespace`` is the ElementTree form, ``{urn:...:pain.002.001.14}``.
    """
    version = namespace.strip("{}").rsplit(":", maxsplit=1)[-1]
    candidate = SCHEMA_DIR / f"{version}.xsd"
    return candidate if candidate.is_file() else None


def parse_pain002_report(
    xml_file_path: str,
    xsd_file_path: str | None = None,
    validate: bool = False,
    *,
    base_dir: str | Path | None = None,
) -> dict[str, object]:
    """Parse a pain.002 payment status report into structured data.

    Args:
        xml_file_path: The bank's pain.002 response.
        xsd_file_path: Explicit schema to validate against. Takes
            precedence over ``validate``.
        validate: Validate against the bundled schema matching the
            document's own namespace. Raises if no bundled schema covers
            that version rather than parsing unvalidated — a silent skip
            would report success while checking nothing. Call
            :func:`bundled_schema_versions` to see what is covered.
        base_dir: Directory the XML path must stay inside. By default
            the path guard allows the working directory, the temp
            directories and the package; a caller that already trusts a
            named file (the CLI's ``status``) passes its directory.

    Returns:
        The parsed report: message and original-message identifiers,
        creation timestamp, group status, and a ``payment_statuses``
        list of per-transaction status and reason codes.

    Schema checks (``xsd_file_path`` or ``validate``) raise
    :class:`~pain001.exceptions.SchemaValidationError` when the document
    fails validation, or when ``validate`` asks for an unbundled version.

    Raises:
        DataSourceError: The path is invalid or the XML is malformed.
    """
    try:
        safe_xml_path = validate_path(
            xml_file_path, base_dir=base_dir, must_exist=True
        )
    except Exception as exc:
        raise DataSourceError(f"Invalid pain.002 XML path: {exc}") from exc

    _check_schema(safe_xml_path, xsd_file_path, validate)
    report, ns = _load_report(safe_xml_path)
    statuses = [
        _payment_status(payment_info, ns)
        for payment_info in report.findall(f"{ns}OrgnlPmtInfAndSts")
    ]
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


def _check_schema(
    safe_xml_path: str, xsd_file_path: str | None, validate: bool
) -> None:
    """Validate against an explicit schema, or the bundled one on request.

    Args:
        safe_xml_path: The report, already through the path guard.
        xsd_file_path: An explicit schema; takes precedence.
        validate: Use the bundled schema for the document's namespace.

    Raises:
        DataSourceError: The schema path is invalid.
        SchemaValidationError: The document failed validation.
    """
    if xsd_file_path:
        try:
            safe_xsd_path = validate_path(xsd_file_path, must_exist=True)
        except Exception as exc:
            raise DataSourceError(f"Invalid pain.002 XSD path: {exc}") from exc
        if not validate_via_xsd(safe_xml_path, safe_xsd_path):
            raise SchemaValidationError(
                f"pain.002 XML failed validation against {safe_xsd_path}"
            )
    elif validate:
        _validate_against_bundled_schema(safe_xml_path)


def _load_report(safe_xml_path: str) -> tuple[Any, str]:
    """Parse the file and return its CstmrPmtStsRpt and namespace.

    Args:
        safe_xml_path: The report, already through the path guard.

    Returns:
        The ``CstmrPmtStsRpt`` element and the ``{namespace}`` prefix.

    Raises:
        DataSourceError: Malformed XML, or not a pain.002 report.
    """
    try:
        root = defused_et.parse(safe_xml_path).getroot()
    except (ParseError, OSError) as exc:
        raise DataSourceError(f"Unable to parse pain.002 XML: {exc}") from exc
    if root is None:  # pragma: no cover - a parsed document always has a root
        raise DataSourceError("pain.002 XML document is empty")

    ns = _detect_namespace(root)
    report = root.find(f".//{ns}CstmrPmtStsRpt")
    if report is None:
        raise DataSourceError(
            "Input XML is not a pain.002 payment status report"
        )
    return report, ns


def _payment_status(payment_info: Any, ns: str) -> dict[str, Any]:
    """Return one OrgnlPmtInfAndSts with every transaction status.

    The first transaction's fields stay at the top level for existing
    callers; every transaction is listed under ``transactions``.

    Args:
        payment_info: The OrgnlPmtInfAndSts element.
        ns: The document namespace in ElementTree search form.

    Returns:
        The block's identifiers and status, and its transactions.
    """
    transactions = [
        _transaction_status(tx, ns)
        for tx in payment_info.findall(f"{ns}TxInfAndSts")
    ]
    record: dict[str, Any] = {
        "original_payment_information_id": _find_text(
            payment_info, ns, "OrgnlPmtInfId"
        ),
        "payment_information_status": _find_text(
            payment_info, ns, "PmtInfSts"
        ),
    }
    if transactions:
        record.update(transactions[0])
    record["transactions"] = transactions
    return record


def _transaction_status(tx_status: Any, ns: str) -> dict[str, str]:
    """Return one TxInfAndSts as a flat record.

    Args:
        tx_status: The TxInfAndSts element.
        ns: The document namespace in ElementTree search form.

    Returns:
        The original EndToEndId, the transaction status and its reason.
    """
    return {
        "original_end_to_end_id": _find_text(tx_status, ns, "OrgnlEndToEndId"),
        "transaction_status": _find_text(tx_status, ns, "TxSts"),
        "status_reason": _find_text(tx_status, ns, "StsRsnInf/Rsn/Cd"),
    }


def _validate_against_bundled_schema(xml_path: str) -> None:
    """Validate against the bundled schema for the document's version.

    Fails loudly when the version is not bundled. The alternative —
    skipping quietly — is how software ends up reporting a successful
    validation it never performed.
    """
    try:
        root = defused_et.parse(xml_path).getroot()
    except ParseError as exc:
        raise DataSourceError(f"Invalid pain.002 XML: {exc}") from exc
    namespace = _detect_namespace(root)
    schema = schema_for_namespace(namespace)
    if schema is None:
        version = (
            namespace.strip("{}").rsplit(":", maxsplit=1)[-1] or "unknown"
        )
        raise SchemaValidationError(
            f"No bundled schema for {version}. Bundled versions are "
            f"{', '.join(bundled_schema_versions())}. Pass xsd_file_path "
            f"with the schema your bank uses, or omit validate to parse "
            f"without schema validation."
        )
    if not validate_via_xsd(xml_path, str(schema)):
        raise SchemaValidationError(
            f"pain.002 XML failed validation against {schema.name}"
        )


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
