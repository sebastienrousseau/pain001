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

"""Berlin Group NextGenPSD2 payment initiation face (ADR-0005).

Target: the JSON request bodies of the NextGenPSD2 XS2A Framework
v1.3.16 (2025-11-27; OpenAPI file under CC BY 4.0): a document with one
transaction becomes ``paymentInitiation_json``, one with several becomes
``bulkPaymentInitiation_json`` with ``paymentInitiationBulkElement_json``
items. Only properties those schemas define are produced; the rest of
the source (instruction identification, purpose, charge bearer, a
single payment's execution date, …) is left to the loss report. The
payment product in the request path is the caller's choice and is not
part of the body.
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
from pain001.faces.paths import Reader

FACE = "berlin_group"
BINDINGS: tuple[str, ...] = ()

_ADDRESS_KEYS = {
    "Department": "department",
    "SubDepartment": "subDepartment",
    "StreetName": "streetName",
    "BuildingNumber": "buildingNumber",
    "BuildingName": "buildingName",
    "Floor": "floor",
    "PostBox": "postBox",
    "Room": "room",
    "PostCode": "postCode",
    "TownName": "townName",
    "TownLocationName": "townLocationName",
    "DistrictName": "districtName",
    "CountrySubDivision": "countrySubDivision",
    "Country": "country",
}


def _account(
    reader: Reader, node: dict[str, Any], path: str, element: str
) -> dict[str, Any] | None:
    """An ``accountReference`` (IBAN or BBAN, plus currency for the debtor)."""
    found = account_id(reader, node, path, element)
    if found is None:
        return None
    out: dict[str, Any] = {found[0]: found[1]}
    currency = reader.text(node, path, element, "Ccy")
    if currency is not None:
        out["currency"] = currency
    return out


def _creditor_address(
    reader: Reader, tx: dict[str, Any], path: str
) -> dict[str, Any] | None:
    """The creditor's ``address``, which the target requires a country for."""
    mark = reader.mark()
    out = address(reader, tx.get("Cdtr", {}), f"{path}/Cdtr", _ADDRESS_KEYS)
    if "country" not in out:
        reader.rollback(mark)
        return None
    return out


def _element(reader: Reader, tx: dict[str, Any], path: str) -> dict[str, Any]:
    """The properties a single payment and a bulk element share."""
    out: dict[str, Any] = {}
    e2e = reader.text(tx, path, "PmtId", "EndToEndId")
    if e2e is not None:
        out["endToEndIdentification"] = e2e
    amount = required(
        reader.amount(
            tx.get("Amt", {}).get("InstdAmt"), f"{path}/Amt/InstdAmt"
        ),
        FACE,
        "CdtTrfTxInf/Amt/InstdAmt",
    )
    out["instructedAmount"] = {"currency": amount[1], "amount": amount[0]}
    out["creditorAccount"] = required(
        _account(reader, tx, path, "CdtrAcct"), FACE, "CdtrAcct (IBAN or BBAN)"
    )
    bic = agent_bic(reader, tx, path, "CdtrAgt")
    if bic is not None:
        out["creditorAgent"] = bic
    agent_name = reader.text(tx, path, "CdtrAgt", "FinInstnId", "Nm")
    if agent_name is not None:
        out["creditorAgentName"] = agent_name
    out["creditorName"] = required(
        reader.text(tx, path, "Cdtr", "Nm"), FACE, "Cdtr/Nm"
    )
    creditor_address = _creditor_address(reader, tx, path)
    if creditor_address is not None:
        out["creditorAddress"] = creditor_address
    lines = tx.get("RmtInf", {}).get("Ustrd")
    if isinstance(lines, list) and lines and isinstance(lines[0], str):
        reader.mapped.add(f"{path}/RmtInf/Ustrd[0]")
        out["remittanceInformationUnstructured"] = lines[0]
    return out


def _execution_date(
    reader: Reader, pmt_inf: dict[str, Any], path: str
) -> str | None:
    """``ReqdExctnDt`` as a date: plain before .08, its ``Dt`` choice after."""
    plain = reader.text(pmt_inf, path, "ReqdExctnDt")
    return (
        plain
        if plain is not None
        else reader.text(pmt_inf, path, "ReqdExctnDt", "Dt")
    )


def _bulk(
    reader: Reader,
    pmt_inf: dict[str, Any],
    path: str,
    payments: list[dict[str, Any]],
    debtor: dict[str, Any],
) -> dict[str, Any]:
    """A ``bulkPaymentInitiation_json`` body."""
    bulk: dict[str, Any] = {}
    batch = reader.text(pmt_inf, path, "BtchBookg")
    if batch is not None:
        bulk["batchBookingPreferred"] = batch == "true"
    bulk["debtorAccount"] = debtor
    purpose = reader.text(pmt_inf, path, "PmtTpInf", "CtgyPurp", "Cd")
    if purpose is not None:
        bulk["categoryPurposeCode"] = purpose
    date = _execution_date(reader, pmt_inf, path)
    if date is not None:
        bulk["requestedExecutionDate"] = date
    bulk["payments"] = payments
    return bulk


def project_berlin_group(
    twin: dict[str, Any],
    bindings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    """Project a pain.001 twin into a NextGenPSD2 payment initiation body.

    Args:
        twin: The ISO JSON twin of the document.
        bindings: Unused: this face takes no side inputs (the engine
            refuses any).

    Returns:
        The request body and the set of source leaf paths it carries.

    A document with no transaction or more than one payment
    information block, or one lacking an element the target requires,
    is refused with a :class:`FaceError`.
    """
    reader = Reader()
    pmt_inf, pi_path = payment_information(twin, FACE)
    debtor = required(
        _account(reader, pmt_inf, pi_path, "DbtrAcct"),
        FACE,
        "DbtrAcct (IBAN or BBAN)",
    )
    txs = transactions(pmt_inf, pi_path)
    payments = [_element(reader, tx, path) for tx, path in txs]
    required(payments or None, FACE, "CdtTrfTxInf")
    if len(payments) == 1:
        return {"debtorAccount": debtor, **payments[0]}, reader.mapped
    return _bulk(reader, pmt_inf, pi_path, payments, debtor), reader.mapped
