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

"""ISO 4217 currency helpers shared by the scheme profiles."""

from collections.abc import Mapping
from typing import Any

from pain001.validation._scheme_types import (
    SchemeValidationResult,
    SchemeViolation,
)

#: ISO 4217 minor-unit exponents that differ from the default of two.
#: Used to bucket amounts before comparing them for duplicates, so
#: ``100`` and ``100.00`` collide while ``100.00`` and ``100.01`` do not.
_CURRENCY_MINOR_UNITS: dict[str, int] = {
    "BIF": 0,
    "CLP": 0,
    "DJF": 0,
    "GNF": 0,
    "ISK": 0,
    "JPY": 0,
    "KMF": 0,
    "KRW": 0,
    "PYG": 0,
    "RWF": 0,
    "UGX": 0,
    "VND": 0,
    "VUV": 0,
    "XAF": 0,
    "XOF": 0,
    "XPF": 0,
    "BHD": 3,
    "IQD": 3,
    "JOD": 3,
    "KWD": 3,
    "LYD": 3,
    "OMR": 3,
    "TND": 3,
}
_DEFAULT_MINOR_UNITS = 2


def _minor_units(currency: str, overrides: Mapping[str, int]) -> int:
    """Return the number of decimal places used to bucket ``currency``.

    Args:
        currency: Upper-cased ISO 4217 code (may be empty).
        overrides: Caller-supplied precision overrides, keyed by code.

    Returns:
        The override when present, else the ISO 4217 minor unit for the
        code, else the default of two.
    """
    if currency in overrides:
        return overrides[currency]
    return _CURRENCY_MINOR_UNITS.get(currency, _DEFAULT_MINOR_UNITS)


def check_currency(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require the payment currency to be EUR.

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    currency = str(row.get("payment_currency", "")).upper()
    if currency != "EUR":
        result.violations.append(
            SchemeViolation(
                rule="SEPA-CCY",
                message=(
                    f"SEPA requires EUR currency (got {currency or 'empty'})"
                ),
                index=index,
                field="payment_currency",
            )
        )


def check_currency_iso(
    row: dict[str, Any], index: int, result: SchemeValidationResult
) -> None:
    """Require a well-formed ISO 4217 currency (any currency, not just EUR).

    Args:
        row: The payment row.
        index: Zero-based row index.
        result: The result accumulator to append violations to.
    """
    currency = str(row.get("payment_currency", "")).strip()
    if not (len(currency) == 3 and currency.isalpha()):
        result.violations.append(
            SchemeViolation(
                rule="XB-CCY",
                message=(
                    "payment_currency must be a 3-letter ISO 4217 code "
                    f"(got {currency or 'empty'})"
                ),
                index=index,
                field="payment_currency",
            )
        )


def check_single_currency(
    data: list[dict[str, Any]], result: SchemeValidationResult
) -> None:
    """Require every row of the batch to share one currency.

    The generator writes all rows into one PmtInf, so a mixed batch
    produces a block CtrlSum that sums amounts across currencies. Rows
    with a malformed currency are left to ``XB-CCY``.

    Args:
        data: All payment rows of the batch.
        result: The result accumulator to append violations to.
    """
    first: str | None = None
    for index, row in enumerate(data):
        currency = str(row.get("payment_currency", "")).strip().upper()
        if not (len(currency) == 3 and currency.isalpha()):
            continue
        if first is None:
            first = currency
        elif currency != first:
            result.violations.append(
                SchemeViolation(
                    rule="XB-CCY-MIX",
                    message=(
                        f"payment_currency {currency} differs from the "
                        f"batch currency {first}; one PmtInf cannot mix "
                        "currencies"
                    ),
                    index=index,
                    field="payment_currency",
                )
            )
