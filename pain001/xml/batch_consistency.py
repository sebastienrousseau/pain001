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

"""Refuse rows that do not share one payment information block.

Every bundled template renders exactly one ``PmtInf``, and its header
(debtor, debtor account and agent, requested execution date, payment
method, batch booking, charge bearer, payment type; for pain.008 the
creditor, sequence type and service level) comes from the first row.
Rows that disagree on one of those columns would be rendered under
row 1's values without a word. This module names, per message type,
the columns each template renders once in ``PmtInf`` (outside the
transaction loop) and refuses a batch whose rows disagree on any of
them.

A later row that leaves such a column blank inherits row 1's value:
callers commonly carry the header on the first row only. A value that
only a later row carries would be dropped, so it is a conflict too.

The GrpHdr (message id, creation time, initiating party) is outside
this rule. The transaction currency is per transaction in every
template; mixing currencies is the cross-border rule's concern
(XB-CCY-MIX), not this one's.
"""

from collections.abc import Sequence
from typing import Any

from pain001.exceptions import PaymentValidationError
from pain001.xml.payment_records import normalize_payment_records

#: A PmtInf column, as the alias chain the preparer reads it through:
#: the effective value is the first non-blank one.
Column = tuple[str, ...]

_PAYMENT_TYPE: tuple[Column, ...] = (
    ("instruction_priority",),
    ("service_level_code",),
    ("local_instrument_code",),
    ("local_instrument_proprietary",),
    ("category_purpose_code",),
)
_DEBTOR_ADDRESS: tuple[Column, ...] = tuple(
    (f"debtor_{key}",)
    for key in (
        "street_name",
        "building_number",
        "postal_code",
        "town_name",
        "country_subdivision",
        "country_code",
        "address_line",
    )
)
_DEBTOR_ACCOUNT: tuple[Column, ...] = tuple(
    (f"debtor_account_{key}",)
    for key in ("IBAN", "number", "scheme", "scheme_proprietary", "currency")
)
_DEBTOR_AGENT: tuple[Column, ...] = tuple(
    (f"debtor_agent_{key}",)
    for key in (
        "BIC",
        "clearing_system",
        "member_id",
        "name",
        "town_name",
        "country_subdivision",
        "country_code",
    )
)
_DEBTOR_ID: tuple[Column, ...] = (
    ("debtor_id",),
    ("debtor_id_scheme",),
    ("debtor_id_scheme_proprietary",),
)

# pain.001.001.03: the .09 context, without LEI or a date-time
# execution date (no element in .03).
_V03: tuple[Column, ...] = (
    ("payment_information_id",),
    ("payment_method",),
    ("batch_booking",),
    *_PAYMENT_TYPE,
    ("requested_execution_date",),
    ("debtor_name",),
    *_DEBTOR_ADDRESS,
    *_DEBTOR_ID,
    *_DEBTOR_ACCOUNT,
    *_DEBTOR_AGENT,
    ("ultimate_debtor_name",),
    ("charge_bearer",),
)
# pain.001.001.09 to .13: .03 plus a date-time execution date and LEI.
_V09: tuple[Column, ...] = (
    *_V03,
    ("requested_execution_datetime",),
    ("debtor_lei",),
)
# pain.001.001.04: PmtInfId is row 1's payment_id (a per-transaction
# column, so a fallback rather than a shared one); the charge bearer is
# per transaction.
_V04: tuple[Column, ...] = (
    ("payment_method",),
    ("batch_booking",),
    ("requested_execution_date",),
    ("debtor_name",),
    ("debtor_street_name",),
    ("debtor_building_number",),
    ("debtor_postal_code",),
    ("debtor_town_name",),
    ("debtor_country_code",),
    ("debtor_account_IBAN",),
    ("debtor_agent_BIC",),
)
# pain.001.001.05 to .08: .04 plus PmtInfId, with the country alias.
_V05: tuple[Column, ...] = (
    ("payment_information_id",),
    *_V04[:-3],
    ("debtor_country_code", "debtor_country"),
    *_V04[-2:],
)
# pain.008.001.02 and .08: the creditor collects, so it heads PmtInf.
_DIRECT_DEBIT: tuple[Column, ...] = (
    ("payment_information_id",),
    ("payment_method",),
    ("batch_booking",),
    ("service_level_code",),
    ("sequence_type",),
    ("requested_execution_date",),
    ("creditor_name",),
    ("creditor_account_IBAN",),
    ("creditor_agent_BIC",),
    ("charge_bearer",),
)

#: Per message type, the columns its template renders once in PmtInf.
PMTINF_COLUMNS: dict[str, tuple[Column, ...]] = {
    "pain.001.001.03": _V03,
    "pain.001.001.04": _V04,
    **{f"pain.001.001.0{v}": _V05 for v in range(5, 9)},
    **{f"pain.001.001.{v:02d}": _V09 for v in range(9, 14)},
    "pain.008.001.02": _DIRECT_DEBIT,
    "pain.008.001.08": _DIRECT_DEBIT,
}

# Compared case-insensitively: the generator renders them in one case.
_CASE_INSENSITIVE = frozenset({"batch_booking"})


def _effective(row: dict[str, Any], column: Column) -> str:
    """The first non-blank value along ``column``'s alias chain."""
    for key in column:
        value = row.get(key)
        text = "" if value is None else str(value).strip()
        if text:
            return text.lower() if key in _CASE_INSENSITIVE else text
    return ""


def _first_conflict(data: Sequence[dict[str, Any]], column: Column) -> int:
    """1-based index of the first row disagreeing with row 1, or 0."""
    reference = _effective(data[0], column)
    for index, row in enumerate(data[1:], start=2):
        value = _effective(row, column)
        if value and value != reference:
            return index
    return 0


def require_single_payment_information(
    data: Sequence[dict[str, Any]], message_type: str
) -> None:
    """Refuse rows that would collapse into another row's PmtInf header.

    Args:
        data: The normalised payment rows of one message.
        message_type: The target message type. One without a column
            table is left to the registry, which reports it.

    Raises:
        PaymentValidationError: Naming every disagreeing column with
            the first row that disagrees with row 1.
    """
    conflicts = []
    for column in PMTINF_COLUMNS.get(message_type, ()):
        index = _first_conflict(data, column)
        if index:
            conflicts.append(f"{column[0]} (row 1 vs row {index})")
    if conflicts:
        raise PaymentValidationError(
            f"Rows for {message_type} do not share one payment "
            f"information block: {', '.join(conflicts)} differ. The "
            "file carries one PmtInf, so these columns take one value "
            "per file: split the rows so each file holds one batch "
            "(one debtor for a transfer, one creditor for a debit).",
            field="records",
        )


def require_one_batch(data: list[dict[str, Any]], message_type: str) -> None:
    """Refuse rows that would not share one payment information block.

    The rows are normalised first, as generation does, so values that
    render the same (``True`` and ``true``) do not conflict. Rows that
    cannot be normalised (a bad amount) are left to the schema check,
    which reports them by row. Disagreeing rows raise the
    ``PaymentValidationError`` of the generation check, naming each
    column and the first row that disagrees with row 1.

    Args:
        data: The loaded payment rows.
        message_type: The target message type.
    """
    try:
        rows = normalize_payment_records(data)
    except PaymentValidationError:
        return
    require_single_payment_information(rows, message_type)
