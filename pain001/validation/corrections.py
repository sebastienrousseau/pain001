# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Deterministic, review-only suggestions for non-financial record fields."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pain001.validation.charset import sanitize_to_charset
from pain001.validation.schema_validator import SchemaValidator

_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_PROTECTED = frozenset(
    {"amount", "payment_amount", "currency", "payment_currency", "ctrl_sum"}
)
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d.%m.%Y",
)


def _refusal(reason: str) -> dict[str, Any]:
    """Return a machine-readable explanation without echoing record data."""
    return {"patches": [], "cannot_autofix": reason}


def _normalise_date(value: str) -> str | None:
    """Return an ISO date only when every matching format agrees."""
    candidates = set()
    for date_format in _DATE_FORMATS:
        if date_format == "%Y%m%d" and not re.fullmatch(r"[0-9]{8}", value):
            continue
        try:
            candidates.add(
                datetime.strptime(value, date_format).date().isoformat()
            )
        except ValueError:
            continue
    return next(iter(candidates)) if len(candidates) == 1 else None


def suggest_record_fix(
    record: dict[str, Any],
    validation_error: dict[str, Any],
    message_type: str = "pain.001.001.03",
) -> dict[str, Any]:
    """Suggest one explicit patch without modifying the supplied record.

    Schema bounds come from bundled schemas, never from an error supplied
    by an agent. Bank identifiers, amounts and currencies are refused even
    for whitespace-only changes. Every candidate requires human review and
    full revalidation; missing-field placeholders are not payment data.
    Unsupported message types propagate ValueError from SchemaValidator.

    Args:
        record: A single flat payment record, which remains unchanged.
        validation_error: An object with ``field`` and ``rule`` keys.
        message_type: Bundled schema supplying field types and length limits.

    Returns:
        An object containing ``patches`` and a ``cannot_autofix`` reason
        when no deterministic candidate is available.

    """
    field = validation_error.get("field", validation_error.get("path", ""))
    if not isinstance(field, str):
        return _refusal("invalid_field")
    field = field.removeprefix("$.")
    if not _FIELD.fullmatch(field):
        return _refusal("invalid_field")
    lower = field.lower()
    if lower in _PROTECTED or any(
        part in lower.split("_")
        for part in ("iban", "bic", "account", "amount", "currency")
    ):
        return _refusal("protected_financial_field")

    schema = SchemaValidator(message_type).schema
    definition = schema["properties"].get(field)
    if definition is None:
        return _refusal("unknown_field")
    rule = validation_error.get("rule")
    value = record.get(field)
    candidate: Any = None
    placeholder = False
    if rule == "CHARSET" and isinstance(value, str):
        candidate = sanitize_to_charset(value)
    elif rule == "FIELD-LENGTH" and isinstance(value, str):
        limit = definition.get("maxLength")
        if isinstance(limit, int):
            candidate = value[:limit]
    elif rule == "DATE-FORMAT" and isinstance(value, str):
        if definition.get("format") == "date":
            candidate = _normalise_date(value)
    elif rule == "MISSING-REQUIRED" and field in schema["required"]:
        if field not in record or value in (None, ""):
            candidate = {
                "string": "REQUIRED",
                "integer": 0,
                "number": 0,
                "boolean": False,
            }.get(definition.get("type"))
            placeholder = True

    if candidate is None or candidate == value:
        return _refusal("no_unambiguous_fix")
    return {
        "patches": [
            {
                "op": "replace" if field in record else "add",
                "path": f"/{field}",
                "value": candidate,
                "rule": rule,
                "requires_review": True,
                "placeholder": placeholder,
            }
        ],
        "cannot_autofix": None,
    }
