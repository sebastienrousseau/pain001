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

"""Normalise payment records into the shape the templates read.

Key aliases, two-decimal amounts, XSD date and boolean forms, and the
batch totals computed from the rows. :mod:`pain001.xml.generate_xml`
renders the result; validation and the streaming writer use the same
normalisation so they see the rows as generation will.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pain001.exceptions import PaymentValidationError

# ISO 20022 amounts carry at most two decimal places.
_AMOUNT_EXPONENT = Decimal("0.01")

# Common caller-side field aliases -> canonical field names. LLM agents and
# ad-hoc integrations naturally say "amount"/"currency"; the schemas and
# templates use payment_amount / payment_currency (the JSON Schemas document
# "currency", the templates read "payment_currency" - both are canonical
# spellings of the same value, so the pair is mirrored bidirectionally).
_FIELD_ALIASES: dict[str, str] = {
    "amount": "payment_amount",
    "instructed_amount": "payment_amount",
    "payment_currency": "currency",
    "currency": "payment_currency",
    "execution_date": "requested_execution_date",
}

# Keys whose canonical spelling carries an upper-case identifier suffix;
# callers frequently produce the all-lower-case form.
_IDENTIFIER_KEYS: dict[str, str] = {
    "debtor_account_iban": "debtor_account_IBAN",
    "creditor_account_iban": "creditor_account_IBAN",
    "debtor_agent_bic": "debtor_agent_BIC",
    "creditor_agent_bic": "creditor_agent_BIC",
    "forwarding_agent_bic": "forwarding_agent_BIC",
    "charge_agent_bicfi": "charge_agent_BICFI",
    "creditor_agent_bicfi": "creditor_agent_BICFI",
    "debtor_agent_account_iban": "debtor_agent_account_IBAN",
    "charge_account_iban": "charge_account_IBAN",
}

_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_SPACE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]")

# Fields rendered into xs:dateTime XML content (e.g. GrpHdr/CreDtTm): a bare
# date is coerced to midnight so "2026-07-18" does not fail XSD validation.
_DATETIME_FIELDS = ("date",)
# Fields rendered into xs:date XML content (e.g. ReqdExctnDt/Dt): a full
# datetime is truncated to its date part.
_DATE_FIELDS = ("requested_execution_date", "reference_date")
# Fields rendered into xs:boolean XML content.
_BOOLEAN_FIELDS = ("batch_booking",)


def _canonicalize_keys(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``row`` with alias keys mapped to canonical names.

    An alias never overwrites an explicitly-provided canonical key with a
    non-empty value.

    Args:
        row: The raw input row.

    Returns:
        A new dict whose keys are the canonical field names.
    """
    updated: dict[str, Any] = dict(row)
    for key, value in row.items():
        canonical = _IDENTIFIER_KEYS.get(key.lower())
        if canonical is None:
            canonical = _FIELD_ALIASES.get(key)
        if canonical is None or canonical == key:
            continue
        existing = updated.get(canonical)
        if existing is None or str(existing).strip() == "":
            updated[canonical] = value
    return updated


def _as_datetime(text: str) -> str:
    """Return ``text`` as an XSD dateTime when it is a bare date or a
    space-separated date-time; otherwise unchanged."""
    if _DATE_ONLY_RE.match(text):
        return f"{text}T00:00:00"
    if _DATETIME_SPACE_RE.match(text):
        return text.replace(" ", "T", 1)
    return text


def _as_date(text: str) -> str:
    """Return the date part of a date-time ``text``; otherwise unchanged."""
    return text[:10] if _DATETIME_RE.match(text) else text


def _as_boolean(text: str) -> str:
    """Return ``true``/``false`` in XSD form for any casing of them;
    otherwise ``text`` unchanged (stripping is left to the caller's
    other fields)."""
    lowered = text.strip().lower()
    return lowered if lowered in ("true", "false") else text


def _coerce_temporal_and_boolean(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce date/datetime/boolean values into their XSD lexical forms.

    Args:
        row: A canonical-key row (mutated in place and returned).

    Returns:
        The same row with temporal and boolean fields in XSD form.
    """
    for fields, coerce, strip in (
        (_DATETIME_FIELDS, _as_datetime, True),
        (_DATE_FIELDS, _as_date, True),
        (_BOOLEAN_FIELDS, _as_boolean, False),
    ):
        for key in fields:
            value = row.get(key)
            if not isinstance(value, str):
                continue
            text = value.strip() if strip else value
            coerced = coerce(text)
            if coerced != text:  # an unmatched value keeps its spacing
                row[key] = coerced
    return row


def _format_amount(value: Any, row_index: int) -> str:
    """Normalize a monetary amount to an exact two-decimal string.

    Amounts are handled with Decimal end-to-end: floats are converted via
    their shortest string representation so binary artifacts are surfaced
    (and rejected) rather than silently rounded into the payment file.

    Args:
        value: The raw amount from the input row.
        row_index: 1-based row number, used in error messages.

    Returns:
        The amount as an exact two-decimal string (e.g. "10.00").

    Raises:
        PaymentValidationError: If the amount is missing, not a number,
            not positive, or carries more than two decimal places.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount is required",
            field="payment_amount",
        )
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as e:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount {value!r} is not a number",
            field="payment_amount",
        ) from e
    if not amount.is_finite() or amount <= 0:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount must be a positive amount, "
            f"got {value!r}",
            field="payment_amount",
        )
    quantized = amount.quantize(_AMOUNT_EXPONENT)
    if amount != quantized:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount {value!r} has more than two "
            "decimal places; round it explicitly before generating",
            field="payment_amount",
        )
    return f"{quantized:.2f}"


def _normalize_financial_fields(
    data: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, str]:
    """Normalize amounts and booleans, computing batch totals from rows.

    Args:
        data: Payment rows, each carrying a "payment_amount" value.

    Returns:
        Tuple of (normalized rows, nb_of_txs, ctrl_sum) where amounts are
        two-decimal strings, booleans are XSD-style "true"/"false", and
        nb_of_txs/ctrl_sum are computed from the data instead of trusting
        caller-provided header fields.
    """
    normalized: list[dict[str, Any]] = []
    total = Decimal("0.00")
    for index, row in enumerate(data, start=1):
        updated = _canonicalize_keys(row)
        formatted = _format_amount(updated.get("payment_amount"), index)
        total += Decimal(formatted)
        # XSD xs:boolean only accepts "true"/"false"; Python bools from
        # typed sources (JSON, SQLite) would otherwise render as "True".
        updated = {
            key: (
                ("true" if value else "false")
                if isinstance(value, bool)
                else value
            )
            for key, value in updated.items()
        }
        updated = _coerce_temporal_and_boolean(updated)
        updated["payment_amount"] = formatted
        normalized.append(updated)
    for updated in normalized:
        # Batch totals are always computed from the rows; caller-supplied
        # values are overwritten so the message stays internally consistent
        # and the header fields never have to be provided by hand. Kept as
        # int/float so the rows also satisfy the JSON Schemas' types.
        updated["nb_of_txs"] = len(normalized)
        updated["ctrl_sum"] = float(total)
    return normalized, str(len(normalized)), f"{total:.2f}"


def canonicalize_payment_record(row: dict[str, Any]) -> dict[str, Any]:
    """Map a record's alias keys to canonical field names, preserving values.

    The key-mapping half of :func:`normalize_payment_records`: ``amount``
    becomes ``payment_amount``, ``currency`` and ``payment_currency``
    mirror each other, and lower-case ``*_iban`` / ``*_bic`` spellings are
    canonicalized - without reformatting any value. Use this before
    JSON-Schema validation, where typed values (numbers, booleans) must
    keep their types.

    Args:
        row: The raw input record.

    Returns:
        A new dict with canonical keys; the input is not mutated.
    """
    return _canonicalize_keys(row)


def normalize_payment_records(
    data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize caller records into the canonical pain.001 input shape.

    Applies the same ergonomics the generators use internally, so records
    can also be pre-normalized before JSON-Schema validation:

    * field aliases (``amount`` -> ``payment_amount``, ``currency`` <->
      ``payment_currency``, lower-case IBAN/BIC key spellings, ...);
    * amounts formatted as exact two-decimal strings;
    * Python/JSON booleans (and ``"True"``/``"FALSE"`` strings) rendered
      in XSD form (``"true"``/``"false"``);
    * bare dates coerced to the XSD lexical form each field requires
      (``date`` -> ``YYYY-MM-DDT00:00:00``, ``requested_execution_date``
      truncated to ``YYYY-MM-DD``);
    * ``nb_of_txs`` and ``ctrl_sum`` computed from the rows themselves.

    Args:
        data: The raw payment rows.

    Returns:
        A new list of normalized rows; the input is not mutated.

    A ``PaymentValidationError`` from amount normalization (missing,
    non-numeric, non-positive, or over-precise payment amounts)
    propagates unchanged.
    """
    normalized, _, _ = _normalize_financial_fields(data)
    return normalized
