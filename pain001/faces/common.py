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

"""Shared navigation for the payment faces (UK Open Banking, Berlin Group).

A face never invents a value: an element the target requires but the
source lacks is refused with a :class:`FaceError` that names it.
"""

from __future__ import annotations

from typing import Any

from pain001.faces.models import FaceError
from pain001.faces.paths import Reader

MESSAGE = "CstmrCdtTrfInitn"

# Postal address elements whose target names differ only in spelling.
ADDRESS_TAGS: tuple[tuple[str, str], ...] = (
    ("Dept", "Department"),
    ("SubDept", "SubDepartment"),
    ("StrtNm", "StreetName"),
    ("BldgNb", "BuildingNumber"),
    ("BldgNm", "BuildingName"),
    ("Flr", "Floor"),
    ("PstBx", "PostBox"),
    ("Room", "Room"),
    ("PstCd", "PostCode"),
    ("TwnNm", "TownName"),
    ("TwnLctnNm", "TownLocationName"),
    ("DstrctNm", "DistrictName"),
    ("CtrySubDvsn", "CountrySubDivision"),
    ("Ctry", "Country"),
)


def payment_information(
    twin: dict[str, Any], face: str
) -> tuple[dict[str, Any], str]:
    """The document's single ``PmtInf`` block and its path.

    Args:
        twin: The ISO JSON twin.
        face: The face name, for the error message.

    Returns:
        The payment information node and its indexed path.

    Raises:
        FaceError: When the document has no payment information block,
            or more than one (both faces take one debtor account and
            one execution date per request).
    """
    message = twin.get("Document", {}).get(MESSAGE)
    blocks = message.get("PmtInf") if isinstance(message, dict) else None
    if not isinstance(blocks, list) or len(blocks) != 1:
        count = len(blocks) if isinstance(blocks, list) else 0
        raise FaceError(
            f"{face}: a request carries one payment information block; "
            f"this document has {count}"
        )
    block: dict[str, Any] = blocks[0]
    return block, f"{MESSAGE}/PmtInf[0]"


def transactions(
    pmt_inf: dict[str, Any], path: str
) -> list[tuple[dict[str, Any], str]]:
    """Each ``CdtTrfTxInf`` of a payment information block with its path."""
    items = pmt_inf.get("CdtTrfTxInf")
    if not isinstance(items, list):
        return []
    return [
        (tx, f"{path}/CdtTrfTxInf[{index}]") for index, tx in enumerate(items)
    ]


def required(value: Any, face: str, what: str) -> Any:
    """Return ``value``, or refuse when the target needs it and it is absent.

    Args:
        value: The projected value, ``None`` when the source lacks it.
        face: The face name, for the error message.
        what: The source element, as a path or a short description.

    Returns:
        ``value`` unchanged.

    Raises:
        FaceError: When ``value`` is ``None``.
    """
    if value is None:
        raise FaceError(
            f"{face}: {what} is required by the target and absent from the "
            "source; a face never invents a value"
        )
    return value


def account_id(
    reader: Reader, node: dict[str, Any], path: str, element: str
) -> tuple[str, str] | None:
    """``("iban", value)`` or ``("bban", value)`` for an account element.

    A BBAN is read only from ``Id/Othr`` whose scheme code is ``BBAN``;
    any other ``Othr`` identification has no counterpart and is left to
    the loss report.

    Args:
        reader: The reader recording mapped leaves.
        node: The node holding the account element.
        path: The indexed path of ``node``.
        element: The account element tag (``DbtrAcct`` or ``CdtrAcct``).

    Returns:
        The identification kind and value, or ``None``.
    """
    account = node.get(element)
    if not isinstance(account, dict):
        return None
    base = f"{path}/{element}"
    iban = reader.text(account, base, "Id", "IBAN")
    if iban is not None:
        return "iban", iban
    other = account.get("Id", {}).get("Othr")
    scheme = (
        other.get("SchmeNm", {}).get("Cd") if isinstance(other, dict) else None
    )
    if scheme != "BBAN":
        return None
    bban = reader.text(account, base, "Id", "Othr", "Id")
    if bban is None:
        return None
    reader.text(account, base, "Id", "Othr", "SchmeNm", "Cd")
    return "bban", bban


def agent_bic(
    reader: Reader, node: dict[str, Any], path: str, element: str
) -> str | None:
    """The BIC of an agent element (``BICFI``, or ``BIC`` before .04)."""
    for tag in ("BICFI", "BIC"):
        bic = reader.text(node, path, element, "FinInstnId", tag)
        if bic is not None:
            return bic
    return None


def address(
    reader: Reader, party: dict[str, Any], path: str, keys: dict[str, str]
) -> dict[str, Any]:
    """Map a party's ``PstlAdr`` to target keys, recording what is used.

    Args:
        reader: The reader recording mapped leaves.
        party: The party node holding ``PstlAdr``.
        path: The indexed path of ``party``.
        keys: Target key for each ISO element name in
            :data:`ADDRESS_TAGS` the target supports, plus
            ``"AddressLine"`` when it supports address lines.

    Returns:
        The target address object, empty when nothing maps.
    """
    out: dict[str, Any] = {}
    for tag, name in ADDRESS_TAGS:
        if name in keys:
            value = reader.text(party, path, "PstlAdr", tag)
            if value is not None:
                out[keys[name]] = value
    if "AddressLine" in keys:
        lines = reader.texts(
            party.get("PstlAdr"), f"{path}/PstlAdr", "AdrLine"
        )
        if lines:
            out[keys["AddressLine"]] = lines
    return out
