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

"""Country purpose-code mandates, each its own validation profile.

:class:`PurposeMandate` adds the five country purpose-code mandates
(AE, QA, MY, GB, HK) the corpus plan names. They carry no rail rules of
their own, so they compose with any rail through the comma syntax
(``--scheme uk-chaps,purpose-mandate-gb``). The row helpers
:func:`row_text` and :func:`purpose_known` are shared with
:mod:`pain001.validation.rails`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pain001.validation._scheme_rules import ValidationProfile
from pain001.validation._scheme_types import (
    SchemeValidationResult,
    SchemeViolation,
)


def row_text(row: dict[str, Any], *keys: str) -> str | None:
    """The first non-blank value among ``keys``, stripped, else ``None``.

    Args:
        row: One payment row.
        *keys: Column names, in order of preference.

    Returns:
        The stripped value, or ``None`` when every key is absent or blank.
    """
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def execution_date(row: dict[str, Any]) -> date | None:
    """The row's requested execution date, or ``None`` when unreadable.

    Args:
        row: One payment row.

    Returns:
        The date of ``requested_execution_date``, else of the date part
        of ``requested_execution_datetime``; ``None`` when neither reads
        as an ISO 8601 date.
    """
    raw = row_text(
        row, "requested_execution_date", "requested_execution_datetime"
    )
    try:
        return date.fromisoformat(raw[:10]) if raw else None
    except ValueError:
        return None


def purpose_known(code: str) -> bool:
    """True when ``code`` is in the vendored ISO external purpose list.

    Args:
        code: A ``Purp/Cd`` value.

    Returns:
        Whether ``ExternalPurpose1Code`` lists it.
    """
    from pain001.corpus.rules.external_codes import is_valid  # noqa: PLC0415

    return is_valid("ExternalPurpose1Code", code)


class PurposeMandate(ValidationProfile):
    """A country's purpose-code mandate, as its own profile.

    Args:
        country: ISO 3166 alpha-2 code.
        title: Human title.
        where: ``purpose`` (Purp/Cd or Prtry) or ``regulatory``
            (RgltryRptg/Dtls), where the country expects the code.
        pattern: Regex the code must match, if the country prescribes one.
        currency: Only when the payment currency is this (HK RMB).
        sources: The public documents the mandate comes from.
    """

    def __init__(
        self,
        country: str,
        title: str,
        where: str,
        pattern: str | None = None,
        currency: str | None = None,
        sources: tuple[str, ...] = (),
    ) -> None:
        self.country = country
        self.title = title
        self.where = where
        self.pattern = re.compile(pattern) if pattern else None
        self.currency = currency
        self.sources = sources
        self.name = f"purpose-mandate-{country.lower()}"

    def validate(self, data: list[dict[str, Any]]) -> SchemeValidationResult:
        """Validate payment rows against the country's purpose mandate.

        Args:
            data: Loaded payment rows.

        Returns:
            A :class:`SchemeValidationResult` listing every violation.
        """
        result = SchemeValidationResult(profile=self.name)
        rule = f"PURP-{self.country}"
        for index, row in enumerate(data):
            finding = self._finding(row)
            if finding is not None:
                message, field_name = finding
                result.violations.append(
                    SchemeViolation(rule, message, index, field_name)
                )
        return result

    def _applies(self, row: dict[str, Any]) -> bool:
        """False when the mandate is limited to another currency."""
        return (
            not self.currency
            or row_text(row, "payment_currency", "currency") == self.currency
        )

    def _code(self, row: dict[str, Any]) -> tuple[str | None, str]:
        """The row's code where the country expects it, and its column."""
        if self.where == "regulatory":
            code = row_text(
                row, "regulatory_reporting_code", "regulatory_reporting_info"
            )
            return code, "regulatory_reporting_code"
        return row_text(row, "purpose_code", "purpose_proprietary"), (
            "purpose_code"
        )

    def _finding(self, row: dict[str, Any]) -> tuple[str, str] | None:
        """The one violation a row carries, as (message, column), or None."""
        if not self._applies(row):
            return None
        code, field_name = self._code(row)
        if not code:
            return f"{self.title}: a purpose code is mandatory", field_name
        if self.pattern is not None and not self.pattern.fullmatch(code):
            return (
                f"{self.title}: purpose code {code} does not match "
                f"{self.pattern.pattern}",
                field_name,
            )
        iso_code = row_text(row, "purpose_code")
        if (
            self.where == "purpose"
            and iso_code
            and not purpose_known(iso_code)
        ):
            return (
                f"{self.title}: purpose code {code} is not in the ISO "
                "external purpose list",
                field_name,
            )
        return None


PURPOSE_MANDATES: tuple[PurposeMandate, ...] = (
    PurposeMandate(
        "AE",
        "UAE CBUAE purpose of payment",
        "regulatory",
        r"(/(BENEFRES|ORDERRES)/AE//)?[A-Z]{3}",
        sources=("CBUAE technical notes on transaction codes (AUX700)",),
    ),
    PurposeMandate(
        "QA",
        "Qatar QCB purpose of payment",
        "purpose",
        sources=("QCB retail payment pages",),
    ),
    PurposeMandate(
        "MY",
        "Malaysia BNM purpose code",
        "purpose",
        sources=("BNM purpose-code lists",),
    ),
    PurposeMandate(
        "GB",
        "UK CHAPS purpose code",
        "purpose",
        sources=("Bank of England ISO 20022 enhanced data in CHAPS",),
    ),
    PurposeMandate(
        "HK",
        "Hong Kong RMB cross-border purpose code",
        "regulatory",
        currency="CNY",
        sources=(
            "A Hong Kong bank's public RMB purpose-code notices",
            "A US bank's public RMB quick guide",
        ),
    ),
)

__all__ = [
    "PURPOSE_MANDATES",
    "PurposeMandate",
    "execution_date",
    "purpose_known",
    "row_text",
]
