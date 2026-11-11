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

"""Project a pain.001 or pain.008 document onto payment rows.

The scheme profiles in :mod:`pain001.validation.schemes` and the rail
profiles in :mod:`pain001.validation.rails` judge rows: the flat,
CSV-shaped records the loaders produce. A corpus file is XML. This
module reads one document back into that row shape, one row per
transaction, so a built file can be judged by the same profiles a CSV
would be, with the payment-information level merged into each row and
the transaction level winning where both carry a value.

Keys follow the CSV column names the validators already read
(``payment_currency``, ``creditor_account_IBAN`` ...) and add the ones
the rail profiles need (``creditor_agent_member_id``, ``purpose_code``,
``uetr``, ``creditor_town`` ...). Values are strings; absent elements
are absent keys.
"""

from __future__ import annotations

from typing import Any

from defusedxml import ElementTree as defused_et


def _local(tag: Any) -> str:
    """The local name of a tag, namespace stripped."""
    return str(tag).rsplit("}", 1)[-1]


def _children(node: Any) -> list[Any]:
    """The element's children, or none for a missing element."""
    return list(node) if node is not None else []


def _child(node: Any, *names: str) -> Any | None:
    """Descend through ``names`` by local name; ``None`` when absent."""
    for name in names:
        if node is None:
            return None
        node = next((c for c in node if _local(c.tag) == name), None)
    return node


def _text(node: Any, *names: str) -> str | None:
    """The stripped text at the end of ``names``, if present."""
    found = _child(node, *names)
    if found is None or found.text is None:
        return None
    text = str(found.text).strip()
    return text or None


def _first_text(node: Any, *paths: tuple[str, ...]) -> str | None:
    """The first of several paths that carries text."""
    for path in paths:
        value = _text(node, *path)
        if value is not None:
            return value
    return None


def _party(node: Any, prefix: str) -> dict[str, str]:
    """Name, address and identification of a party block."""
    row: dict[str, str] = {}
    if node is None:
        return row
    fields = {
        "name": _text(node, "Nm"),
        "town": _text(node, "PstlAdr", "TwnNm"),
        "country": _text(node, "PstlAdr", "Ctry"),
        "post_code": _text(node, "PstlAdr", "PstCd"),
        "street_name": _text(node, "PstlAdr", "StrtNm"),
        "address_lines": "|".join(
            str(line.text).strip()
            for line in _children(_child(node, "PstlAdr"))
            if _local(line.tag) == "AdrLine" and line.text
        )
        or None,
        "lei": _text(node, "Id", "OrgId", "LEI"),
        "bic": _first_text(
            node, ("Id", "OrgId", "AnyBIC"), ("Id", "OrgId", "BICOrBEI")
        ),
        "other_id": _first_text(
            node, ("Id", "OrgId", "Othr", "Id"), ("Id", "PrvtId", "Othr", "Id")
        ),
        "other_id_scheme": _first_text(
            node,
            ("Id", "OrgId", "Othr", "SchmeNm", "Cd"),
            ("Id", "OrgId", "Othr", "SchmeNm", "Prtry"),
            ("Id", "PrvtId", "Othr", "SchmeNm", "Cd"),
            ("Id", "PrvtId", "Othr", "SchmeNm", "Prtry"),
        ),
        "country_of_residence": _text(node, "CtryOfRes"),
    }
    for key, value in fields.items():
        if value is not None:
            row[f"{prefix}_{key}"] = value
    return row


def _account(node: Any, prefix: str) -> dict[str, str]:
    """IBAN or other id, currency, proxy of a cash account block."""
    row: dict[str, str] = {}
    if node is None:
        return row
    fields = {
        "IBAN": _text(node, "Id", "IBAN"),
        "id": _text(node, "Id", "Othr", "Id"),
        "id_scheme": _first_text(
            node,
            ("Id", "Othr", "SchmeNm", "Cd"),
            ("Id", "Othr", "SchmeNm", "Prtry"),
        ),
        "currency": _text(node, "Ccy"),
        "type": _first_text(node, ("Tp", "Cd"), ("Tp", "Prtry")),
        "proxy_type": _first_text(
            node, ("Prxy", "Tp", "Cd"), ("Prxy", "Tp", "Prtry")
        ),
        "proxy_id": _text(node, "Prxy", "Id"),
    }
    for key, value in fields.items():
        if value is not None:
            row[f"{prefix}_{key}"] = value
    return row


def _agent(node: Any, prefix: str) -> dict[str, str]:
    """BIC, clearing member id, LEI and name of an agent block."""
    row: dict[str, str] = {}
    if node is None:
        return row
    fin = _child(node, "FinInstnId")
    fields = {
        "BIC": _first_text(fin, ("BICFI",), ("BIC",)),
        "clearing_system": _first_text(
            fin,
            ("ClrSysMmbId", "ClrSysId", "Cd"),
            ("ClrSysMmbId", "ClrSysId", "Prtry"),
        ),
        "member_id": _text(fin, "ClrSysMmbId", "MmbId"),
        "lei": _text(fin, "LEI"),
        "name": _text(fin, "Nm"),
        "other_id": _text(fin, "Othr", "Id"),
    }
    for key, value in fields.items():
        if value is not None:
            row[f"{prefix}_{key}"] = value
    return row


def _payment_type(node: Any) -> dict[str, str]:
    """Service level, local instrument, category purpose, priority, sequence."""
    row: dict[str, str] = {}
    if node is None:
        return row
    fields = {
        "instruction_priority": _text(node, "InstrPrty"),
        "service_level_code": _text(node, "SvcLvl", "Cd"),
        "service_level_proprietary": _text(node, "SvcLvl", "Prtry"),
        "local_instrument_code": _text(node, "LclInstrm", "Cd"),
        "local_instrument_proprietary": _text(node, "LclInstrm", "Prtry"),
        "category_purpose_code": _text(node, "CtgyPurp", "Cd"),
        "category_purpose_proprietary": _text(node, "CtgyPurp", "Prtry"),
        "sequence_type": _text(node, "SeqTp"),
    }
    for key, value in fields.items():
        if value is not None:
            row[key] = value
    return row


def _remittance(tx: Any) -> dict[str, str]:
    """Unstructured lines and the first structured creditor reference."""
    row: dict[str, str] = {}
    rmt = _child(tx, "RmtInf")
    if rmt is None:
        return row
    lines = [
        str(u.text).strip() for u in rmt if _local(u.tag) == "Ustrd" and u.text
    ]
    if lines:
        row["remittance_information"] = " ".join(lines)
    strd = _child(rmt, "Strd")
    if strd is not None:
        fields = {
            "creditor_reference": _text(strd, "CdtrRefInf", "Ref"),
            "creditor_reference_type": _first_text(
                strd,
                ("CdtrRefInf", "Tp", "CdOrPrtry", "Cd"),
                ("CdtrRefInf", "Tp", "CdOrPrtry", "Prtry"),
            ),
            "creditor_reference_issuer": _text(
                strd, "CdtrRefInf", "Tp", "Issr"
            ),
        }
        for key, value in fields.items():
            if value is not None:
                row[key] = value
    return row


def _regulatory(tx: Any) -> dict[str, str]:
    """The first regulatory-reporting code and information line."""
    row: dict[str, str] = {}
    rgltry = _child(tx, "RgltryRptg")
    if rgltry is None:
        return row
    fields = {
        "regulatory_reporting_indicator": _text(rgltry, "DbtCdtRptgInd"),
        "regulatory_reporting_code": _first_text(
            rgltry, ("Dtls", "Cd"), ("Dtls", "RptgCd"), ("Dtls", "Tp", "Cd")
        ),
        "regulatory_reporting_info": _text(rgltry, "Dtls", "Inf"),
        "regulatory_reporting_country": _text(rgltry, "Dtls", "Ctry"),
    }
    for key, value in fields.items():
        if value is not None:
            row[key] = value
    return row


def _present(fields: dict[str, str | None]) -> dict[str, str]:
    """The fields that carry a value, in order."""
    return {k: v for k, v in fields.items() if v is not None}


def _currency(ccy: str | None) -> dict[str, str]:
    """The payment currency, under both column names, when non-empty."""
    return {"payment_currency": ccy, "currency": ccy} if ccy else {}


def _has_text(node: Any) -> bool:
    """Whether ``node`` exists and carries non-blank text."""
    return (
        node is not None and bool(node.text) and bool(str(node.text).strip())
    )


def _equivalent_amount(eqvt: Any) -> dict[str, str]:
    """An equivalent amount, its currency, and the currency of transfer."""
    row: dict[str, str] = {}
    amount: Any = _child(eqvt, "Amt")
    if _has_text(amount):
        row["payment_amount"] = str(amount.text).strip()
        row["equivalent_amount_currency"] = amount.get("Ccy") or ""
    row.update(_currency(_text(eqvt, "CcyOfTrf")))
    return row


def _amount(tx: Any) -> dict[str, str]:
    """Instructed or equivalent amount with its currency."""
    instd: Any = _child(tx, "Amt", "InstdAmt")
    if instd is None:
        instd = _child(tx, "InstdAmt")
    if _has_text(instd):
        return {
            "payment_amount": str(instd.text).strip(),
            **_currency(instd.get("Ccy")),
        }
    eqvt = _child(tx, "Amt", "EqvtAmt")
    return _equivalent_amount(eqvt) if eqvt is not None else {}


def _document_body(root: Any) -> tuple[Any, bool]:
    """The message body and whether it is a direct debit (pain.008)."""
    body = _child(root, "CstmrCdtTrfInitn")
    if body is not None:
        return body, False
    body = _child(root, "CstmrDrctDbtInitn")
    if body is None:
        raise ValueError("not a pain.001 or pain.008 document")
    return body, True


def _group_header(body: Any) -> dict[str, str]:
    """The group-header values every row carries."""
    header = _child(body, "GrpHdr")
    return _present(
        {
            "id": _text(header, "MsgId"),
            "date": _text(header, "CreDtTm"),
            "nb_of_txs": _text(header, "NbOfTxs"),
            "ctrl_sum": _text(header, "CtrlSum"),
            "initiator_name": _text(header, "InitgPty", "Nm"),
        }
    )


def _creditor_scheme_id(node: Any, *prefix: str) -> dict[str, str]:
    """The creditor scheme identifier under ``prefix``, private or org."""
    scheme = _first_text(
        node,
        (*prefix, "CdtrSchmeId", "Id", "PrvtId", "Othr", "Id"),
        (*prefix, "CdtrSchmeId", "Id", "OrgId", "Othr", "Id"),
    )
    return {"creditor_id": scheme} if scheme else {}


def _block_parties(pmt: Any, direct_debit: bool) -> dict[str, str]:
    """The payment-information level party: creditor or debtor side."""
    row: dict[str, str] = {}
    if direct_debit:
        row.update(_party(_child(pmt, "Cdtr"), "creditor"))
        row.update(_account(_child(pmt, "CdtrAcct"), "creditor_account"))
        row.update(_agent(_child(pmt, "CdtrAgt"), "creditor_agent"))
        row.update(_party(_child(pmt, "UltmtCdtr"), "ultimate_creditor"))
        row.update(_creditor_scheme_id(pmt))
    else:
        row.update(_party(_child(pmt, "Dbtr"), "debtor"))
        row.update(_account(_child(pmt, "DbtrAcct"), "debtor_account"))
        row.update(_agent(_child(pmt, "DbtrAgt"), "debtor_agent"))
        row.update(_party(_child(pmt, "UltmtDbtr"), "ultimate_debtor"))
    return row


def _block_level(
    pmt: Any, common: dict[str, str], direct_debit: bool
) -> dict[str, str]:
    """The values one payment-information block gives its transactions."""
    level = dict(common)
    level.update(
        _present(
            {
                "payment_information_id": _text(pmt, "PmtInfId"),
                "payment_method": _text(pmt, "PmtMtd"),
                "batch_booking": _text(pmt, "BtchBookg"),
                "requested_execution_date": _first_text(
                    pmt,
                    ("ReqdExctnDt",),
                    ("ReqdExctnDt", "Dt"),
                    ("ReqdExctnDt", "DtTm"),
                    ("ReqdColltnDt",),
                ),
                "charge_bearer": _text(pmt, "ChrgBr"),
            }
        )
    )
    level.update(_payment_type(_child(pmt, "PmtTpInf")))
    level.update(_block_parties(pmt, direct_debit))
    return level


def _debit_parties(tx: Any) -> dict[str, str]:
    """A direct debit's debtor side, mandate and creditor scheme id."""
    row: dict[str, str] = {}
    row.update(_party(_child(tx, "Dbtr"), "debtor"))
    row.update(_account(_child(tx, "DbtrAcct"), "debtor_account"))
    row.update(_agent(_child(tx, "DbtrAgt"), "debtor_agent"))
    row.update(_party(_child(tx, "UltmtDbtr"), "ultimate_debtor"))
    mandate = _child(tx, "DrctDbtTx", "MndtRltdInf")
    row.update(
        _present(
            {
                "mandate_id": _text(mandate, "MndtId"),
                "date_of_signature": _text(mandate, "DtOfSgntr"),
                "amendment_indicator": _text(mandate, "AmdmntInd"),
            }
        )
    )
    row.update(_creditor_scheme_id(tx, "DrctDbtTx"))
    return row


def _transfer_parties(tx: Any) -> dict[str, str]:
    """A credit transfer's creditor side and intermediary agents."""
    row: dict[str, str] = {}
    row.update(_party(_child(tx, "Cdtr"), "creditor"))
    row.update(_account(_child(tx, "CdtrAcct"), "creditor_account"))
    row.update(_agent(_child(tx, "CdtrAgt"), "creditor_agent"))
    row.update(_party(_child(tx, "UltmtCdtr"), "ultimate_creditor"))
    row.update(_party(_child(tx, "UltmtDbtr"), "ultimate_debtor"))
    for n in (1, 2, 3):
        row.update(
            _agent(_child(tx, f"IntrmyAgt{n}"), f"intermediary_agent_{n}")
        )
    return row


def _transaction_row(
    tx: Any, level: dict[str, str], direct_debit: bool
) -> dict[str, str]:
    """One transaction's row, its own values winning over the block's."""
    row = dict(level)
    row.update(
        _present(
            {
                "payment_id": _text(tx, "PmtId", "EndToEndId"),
                "end_to_end_id": _text(tx, "PmtId", "EndToEndId"),
                "instruction_id": _text(tx, "PmtId", "InstrId"),
                "uetr": _text(tx, "PmtId", "UETR"),
                "charge_bearer": _text(tx, "ChrgBr"),
                "purpose_code": _text(tx, "Purp", "Cd"),
                "purpose_proprietary": _text(tx, "Purp", "Prtry"),
                "instruction_for_creditor_agent": _text(
                    tx, "InstrForCdtrAgt", "Cd"
                ),
                "instruction_for_debtor_agent": _text(tx, "InstrForDbtrAgt"),
                "cheque_type": _text(tx, "ChqInstr", "ChqTp"),
            }
        )
    )
    row.update(_payment_type(_child(tx, "PmtTpInf")))
    row.update(_amount(tx))
    row.update(_remittance(tx))
    row.update(_regulatory(tx))
    if direct_debit:
        row.update(_debit_parties(tx))
    else:
        row.update(_transfer_parties(tx))
    return row


def rows_from_xml(xml: str) -> list[dict[str, str]]:
    """One row per transaction, payment-information values merged in.

    A document of neither message family propagates ValueError.

    Args:
        xml: A pain.001 or pain.008 document.

    Returns:
        The rows, in document order.
    """
    body, direct_debit = _document_body(defused_et.fromstring(xml))
    common = _group_header(body)
    tx_name = "DrctDbtTxInf" if direct_debit else "CdtTrfTxInf"
    rows: list[dict[str, str]] = []
    for pmt in (c for c in body if _local(c.tag) == "PmtInf"):
        level = _block_level(pmt, common, direct_debit)
        rows.extend(
            _transaction_row(tx, level, direct_debit)
            for tx in pmt
            if _local(tx.tag) == tx_name
        )
    return rows


__all__ = ["rows_from_xml"]
