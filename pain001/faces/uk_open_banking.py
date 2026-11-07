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

"""UK Open Banking domestic payment face (ADR-0005).

Target: the request body of ``POST /domestic-payment-consents``,
``OBWriteDomesticConsent4``, in the Open Banking Read/Write API v4.0.1
(Open Banking Limited, MIT Open Licence). When the private bindings
supply a ``ConsentId`` the same initiation becomes the
``OBWriteDomestic2`` body of ``POST /domestic-payments``.

A domestic payment carries one payment, so the face takes a document
with exactly one transaction. Scheme names come from the Open Banking
internal code set: ``UK.OBIE.IBAN`` for accounts, ``UK.OBIE.BICFI`` for
the creditor agent. Elements without a counterpart (local instrument,
purpose, charge bearer, execution date, regulatory reporting, …) are
left to the loss report rather than translated by guesswork.
"""

from __future__ import annotations

from typing import Any

from pain001.faces.common import (
    account_id,
    address,
    agent_bic,
    payment_information,
    required,
    transactions,
)
from pain001.faces.models import FaceError
from pain001.faces.paths import Reader

FACE = "uk_open_banking"
BINDINGS = ("ConsentId", "Risk")

_ADDRESS_KEYS = {
    name: name
    for name in (
        "Department",
        "SubDepartment",
        "StreetName",
        "BuildingNumber",
        "BuildingName",
        "Floor",
        "PostBox",
        "Room",
        "PostCode",
        "TownName",
        "TownLocationName",
        "DistrictName",
        "CountrySubDivision",
        "Country",
        "AddressLine",
    )
}


def _account(
    reader: Reader,
    node: dict[str, Any],
    path: str,
    element: str,
    party: str,
) -> dict[str, Any] | None:
    """An ``OBCashAccount`` for an IBAN account, with the party's name."""
    mark = reader.mark()
    found = account_id(reader, node, path, element)
    if found is None or found[0] != "iban":
        reader.rollback(mark)
        return None
    out: dict[str, Any] = {
        "SchemeName": "UK.OBIE.IBAN",
        "Identification": found[1],
    }
    name = reader.text(node, path, party, "Nm")
    if name is not None:
        out["Name"] = name
    return out


def _remittance(
    reader: Reader, tx: dict[str, Any], path: str
) -> dict[str, Any]:
    """``RemittanceInformation``: unstructured lines and creditor references."""
    rmt = tx.get("RmtInf")
    base = f"{path}/RmtInf"
    out: dict[str, Any] = {}
    lines = reader.texts(rmt, base, "Ustrd")
    if lines:
        out["Unstructured"] = lines
    structured = rmt.get("Strd") if isinstance(rmt, dict) else None
    refs = []
    for index, item in enumerate(structured or []):
        ref = reader.text(item, f"{base}/Strd[{index}]", "CdtrRefInf", "Ref")
        if ref is not None:
            refs.append({"CreditorReferenceInformation": {"Reference": ref}})
    if refs:
        out["Structured"] = refs
    return out


def _ultimate(
    reader: Reader, tx: dict[str, Any], path: str, tag: str
) -> dict[str, Any] | None:
    """``UltimateCreditor`` / ``UltimateDebtor`` by name, when present."""
    name = reader.text(tx, path, tag, "Nm")
    return {"Name": name} if name is not None else None


def _initiation(
    reader: Reader,
    pmt_inf: dict[str, Any],
    pi_path: str,
    tx: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    """The ``Initiation`` object of one transaction."""
    amount = required(
        reader.amount(
            tx.get("Amt", {}).get("InstdAmt"), f"{path}/Amt/InstdAmt"
        ),
        FACE,
        "CdtTrfTxInf/Amt/InstdAmt",
    )
    initiation: dict[str, Any] = {
        "InstructionIdentification": required(
            reader.text(tx, path, "PmtId", "InstrId"), FACE, "PmtId/InstrId"
        ),
        "EndToEndIdentification": required(
            reader.text(tx, path, "PmtId", "EndToEndId"),
            FACE,
            "PmtId/EndToEndId",
        ),
        "InstructedAmount": {"Amount": amount[0], "Currency": amount[1]},
    }
    debtor = _account(reader, pmt_inf, pi_path, "DbtrAcct", "Dbtr")
    if debtor is not None:
        initiation["DebtorAccount"] = debtor
    bic = agent_bic(reader, tx, path, "CdtrAgt")
    if bic is not None:
        initiation["CreditorAgent"] = {
            "SchemeName": "UK.OBIE.BICFI",
            "Identification": bic,
        }
    creditor = required(
        _account(reader, tx, path, "CdtrAcct", "Cdtr"),
        FACE,
        "CdtrAcct/Id/IBAN",
    )
    required(creditor.get("Name"), FACE, "Cdtr/Nm")
    initiation["CreditorAccount"] = creditor
    _optional(
        initiation,
        "CreditorPostalAddress",
        address(reader, tx.get("Cdtr", {}), f"{path}/Cdtr", _ADDRESS_KEYS),
    )
    _optional(
        initiation,
        "UltimateCreditor",
        _ultimate(reader, tx, path, "UltmtCdtr"),
    )
    _optional(
        initiation, "UltimateDebtor", _ultimate(reader, tx, path, "UltmtDbtr")
    )
    _optional(
        initiation, "RemittanceInformation", _remittance(reader, tx, path)
    )
    return initiation


def _optional(target: dict[str, Any], key: str, value: Any) -> None:
    """Set ``target[key]`` when ``value`` is a non-empty object."""
    if value:
        target[key] = value


def project_uk_open_banking(
    twin: dict[str, Any],
    bindings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    """Project a one-transaction pain.001 twin into a UK Open Banking body.

    Args:
        twin: The ISO JSON twin of the document.
        bindings: Private side inputs: ``ConsentId`` (makes the body an
            ``OBWriteDomestic2``) and ``Risk`` (the ``OBRisk1`` object,
            which has no pain.001 source).

    Returns:
        The request body and the set of source leaf paths it carries.

    Raises:
        FaceError: When the document has more than one transaction, or
            lacks an element the target requires.
    """
    reader = Reader()
    pmt_inf, pi_path = payment_information(twin, FACE)
    txs = transactions(pmt_inf, pi_path)
    if len(txs) != 1:
        raise FaceError(
            f"{FACE}: a domestic payment carries one transaction; this "
            f"document has {len(txs)}"
        )
    tx, path = txs[0]
    data: dict[str, Any] = {}
    bindings = bindings or {}
    if "ConsentId" in bindings:
        data["ConsentId"] = bindings["ConsentId"]
    data["Initiation"] = _initiation(reader, pmt_inf, pi_path, tx, path)
    risk = bindings.get("Risk", {})
    if not isinstance(risk, dict):
        raise FaceError(f"{FACE}: the Risk binding must be an object")
    return {"Data": data, "Risk": dict(risk)}, reader.mapped
