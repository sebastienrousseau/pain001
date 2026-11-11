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


#: Name parts that mark a bank identifier, amount or currency field.
_PROTECTED_PARTS = ("iban", "bic", "account", "amount", "currency")
#: Rules whose fix is derived from the field's current string value.
_STRING_RULES = frozenset({"CHARSET", "FIELD-LENGTH", "DATE-FORMAT"})
#: Missing-field placeholders by JSON Schema type; not payment data.
_PLACEHOLDERS: dict[Any, Any] = {
    "string": "REQUIRED",
    "integer": 0,
    "number": 0,
    "boolean": False,
}


def _field_refusal(field: Any) -> str | None:
    """Why the named field cannot be patched, or ``None`` if it can."""
    if not isinstance(field, str) or not _FIELD.fullmatch(field):
        return "invalid_field"
    lower = field.lower()
    if lower in _PROTECTED or any(
        part in lower.split("_") for part in _PROTECTED_PARTS
    ):
        return "protected_financial_field"
    return None


def _string_candidate(
    rule: Any, value: str, definition: dict[str, Any]
) -> Any:
    """The fix a string rule derives from the value, or ``None``."""
    if rule == "CHARSET":
        return sanitize_to_charset(value)
    if rule == "FIELD-LENGTH":
        limit = definition.get("maxLength")
        return value[:limit] if isinstance(limit, int) else None
    if definition.get("format") == "date":
        return _normalise_date(value)
    return None


def _candidate(
    rule: Any,
    field: str,
    record: dict[str, Any],
    definition: dict[str, Any],
    required: Any,
) -> tuple[Any, bool]:
    """The candidate value for ``field`` and whether it is a placeholder."""
    value = record.get(field)
    if rule in _STRING_RULES:
        if not isinstance(value, str):
            return None, False
        return _string_candidate(rule, value, definition), False
    if (
        rule == "MISSING-REQUIRED"
        and field in required
        and (field not in record or value in (None, ""))
    ):
        return _PLACEHOLDERS.get(definition.get("type")), True
    return None, False


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
    if isinstance(field, str):
        field = field.removeprefix("$.")
    reason = _field_refusal(field)
    if reason is not None:
        return _refusal(reason)

    schema = SchemaValidator(message_type).schema
    definition = schema["properties"].get(field)
    if definition is None:
        return _refusal("unknown_field")
    rule = validation_error.get("rule")
    candidate, placeholder = _candidate(
        rule, field, record, definition, schema["required"]
    )
    if candidate is None or candidate == record.get(field):
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
