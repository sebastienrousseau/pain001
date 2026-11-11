# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Bounded, request-local CEL policies implementing the scheme contract."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import celpy
import holidays
import yaml
from celpy import celtypes
from celpy.celparser import CELParseError
from celpy.evaluation import CELFunction
from lark import Token, Tree

from pain001.constants import VERSION
from pain001.plugins import PluginMeta, SchemeFinding, SchemeResult
from pain001.validation.iban_validator import validate_iban_safe
from pain001.validation.schema_validator import SchemaValidator
from pain001.validation.schemes import (
    SchemeValidationResult,
    SchemeViolation,
    validate_scheme,
)

__all__ = [
    "CustomRuleScheme",
    "MAX_POLICY_BYTES",
    "validate_policy",
]

MAX_POLICY_BYTES = 65536
MAX_RULES = 64
MAX_EXPRESSION_LENGTH = 2048
_IDENTIFIER = re.compile(r"[A-Z][A-Z0-9_-]{0,63}\Z")
_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_METHODS = frozenset({"startsWith", "endsWith", "contains", "matches", "size"})


def _iso_date(value: str) -> date:
    """Parse an explicit ISO calendar date without locale-dependent rules."""
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use ISO dates in YYYY-MM-DD format.")
    return date.fromisoformat(value)


def day_of_week(value: str) -> celtypes.StringType:
    """Return a stable English weekday for an ISO date."""
    return celtypes.StringType(_WEEKDAYS[_iso_date(value).weekday()])


def country_of_iban(value: str) -> celtypes.StringType:
    """Return an IBAN's country only after validating the identifier."""
    value = value.replace(" ", "").replace("-", "").upper()
    if not validate_iban_safe(value):
        raise ValueError("country_of_iban requires a valid IBAN.")
    return celtypes.StringType(value[:2])


def is_business_day(value: str, country: str) -> celtypes.BoolType:
    """Check weekdays and national public holidays, not bank settlement rules."""
    day = _iso_date(value)
    if not 1900 <= day.year <= 2100:
        raise ValueError(
            "Business-day calendars support years 1900 through 2100."
        )
    calendar = holidays.country_holidays(str(country), years=day.year)
    return celtypes.BoolType(day.weekday() < 5 and day not in calendar)


def decimal(value: str) -> Decimal:
    """Parse an exact, finite decimal threshold from a string."""
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("decimal() requires a short decimal string.")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Policy numbers must be finite.")
    return result


_FUNCTIONS = {
    "day_of_week": day_of_week,
    "country_of_iban": country_of_iban,
    "is_business_day": is_business_day,
    "decimal": decimal,
}


@dataclass(frozen=True)
class _Rule:
    """A validated rule and its reusable interpreted CEL program."""

    identifier: str
    severity: str
    message: str
    program: celpy.Runner
    fields: frozenset[str]


def _check_function(name: str) -> None:
    """Refuse a function call outside the policy's own functions."""
    if name == "currency_of_iban":
        raise ValueError(
            "An IBAN does not encode account currency; use the record's currency field."
        )
    if name not in _FUNCTIONS:
        raise ValueError(f"Function {name!r} is not allowed.")


def _check_node(node: Tree[Token]) -> None:
    """Refuse one expression node: a call, method or literal not allowed."""
    if node.data == "ident_arg":
        _check_function(str(node.children[0]))
    if node.data == "member_dot_arg" and str(node.children[1]) not in _METHODS:
        raise ValueError(
            "Only bounded string methods are allowed; CEL collection macros are disabled."
        )
    if (
        node.data == "literal"
        and isinstance(node.children[0], Token)
        and node.children[0].type == "FLOAT_LIT"
    ):
        raise ValueError(
            'Use decimal("1.23") instead of a floating-point literal.'
        )


def _check_expression(tree: Tree[Token]) -> None:
    """Reject unbounded macros, unknown functions and inexact literals."""
    nodes = list(tree.iter_subtrees())
    if len(nodes) > 512:
        raise ValueError("Expression exceeds the 512-node limit.")
    for node in nodes:
        _check_node(node)


_FORBIDDEN_YAML_TOKENS = (
    yaml.tokens.AliasToken,
    yaml.tokens.AnchorToken,
    yaml.tokens.TagToken,
)
_RULE_KEYS = frozenset({"id", "where", "severity", "message"})


def _parse_specs(source: str) -> list[Any]:
    """Parse the policy YAML into its rule specs, refusing YAML features."""
    if len(source.encode("utf-8")) > MAX_POLICY_BYTES:
        raise ValueError("Policy exceeds the 64 KiB limit.")
    try:
        for token in yaml.scan(source):
            if isinstance(token, _FORBIDDEN_YAML_TOKENS):
                raise ValueError(
                    "YAML aliases, anchors and explicit tags are not allowed in policies."
                )
        specs = yaml.safe_load(source)
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError("Invalid policy YAML.") from exc
    if not isinstance(specs, list) or not 1 <= len(specs) <= MAX_RULES:
        raise ValueError("A policy must contain between 1 and 64 rules.")
    return specs


def _rule_identifier(spec: Any, seen: set[str]) -> str:
    """The rule's ID, once its keys and the ID itself are checked."""
    if not isinstance(spec, dict) or set(spec) != _RULE_KEYS:
        raise ValueError(
            "Each rule requires exactly id, where, severity and message."
        )
    identifier = spec["id"]
    if (
        not isinstance(identifier, str)
        or not _IDENTIFIER.fullmatch(identifier)
        or identifier in seen
    ):
        raise ValueError(
            "Rule IDs must be unique uppercase identifiers of at most 64 characters."
        )
    return identifier


def _check_rule_fields(expression: Any, severity: Any, message: Any) -> None:
    """Refuse a where, severity or message outside its allowed form."""
    if (
        not isinstance(expression, str)
        or not 1 <= len(expression) <= MAX_EXPRESSION_LENGTH
    ):
        raise ValueError(
            "where must be a CEL string of 1 through 2048 characters."
        )
    if severity not in ("error", "warning", "info"):
        raise ValueError("severity must be error, warning or info.")
    if not isinstance(message, str) or not 1 <= len(message) <= 1024:
        raise ValueError(
            "message must be a string of 1 through 1024 characters."
        )


def _compile_rule(
    environment: celpy.Environment, spec: dict[str, Any], identifier: str
) -> _Rule:
    """Check and compile one rule spec; errors name the rule."""
    try:
        expression, severity, message = (
            spec["where"],
            spec["severity"],
            spec["message"],
        )
        _check_rule_fields(expression, severity, message)
        tree = environment.compile(expression)
        _check_expression(tree)
        # CEL supports custom scalar values at runtime. Decimal is kept
        # exact instead of being coerced to the library's binary double.
        functions: dict[str, CELFunction] = cast(
            "dict[str, CELFunction]", _FUNCTIONS
        )
        program = environment.program(tree, functions=functions)
    except (
        ValueError,
        TypeError,
        CELParseError,
        RecursionError,
    ) as exc:
        raise ValueError(f"Rule {identifier}: {exc}") from exc
    fields = frozenset(
        str(node.children[0]) for node in tree.find_data("ident")
    )
    return _Rule(identifier, severity, message, program, fields)


def _load_rules(source: str) -> list[_Rule]:
    """Validate YAML and compile bounded CEL without evaluating any record."""
    specs = _parse_specs(source)
    rules = []
    seen: set[str] = set()
    environment = celpy.Environment()
    for spec in specs:
        identifier = _rule_identifier(spec, seen)
        seen.add(identifier)
        rules.append(_compile_rule(environment, spec, identifier))
    return rules


_EXACT_FIELDS = frozenset({"amount", "payment_amount", "ctrl_sum"})


def _string(value: str) -> celtypes.StringType:
    """A bounded CEL string."""
    if len(value) > 4096:
        raise ValueError(
            "Policy string inputs must be at most 4096 characters."
        )
    return celtypes.StringType(value)


def _scalar(name: str, value: Any, expected: Any) -> Any:
    """One record value as a CEL scalar, exact for monetary numbers."""
    if expected == "number" or name in _EXACT_FIELDS:
        return decimal(str(value))
    if isinstance(value, bool):
        return celtypes.BoolType(value)
    if expected == "integer" or isinstance(value, int):
        return celtypes.IntType(int(value))
    if isinstance(value, float | Decimal):
        return decimal(str(value))
    if isinstance(value, str):
        return _string(value)
    if value is None:
        return None
    raise ValueError("Policy inputs must be flat scalar records.")


def _activation(
    row: dict[str, Any], properties: dict[str, Any]
) -> dict[str, Any]:
    """Expose only bounded scalar values, preserving exact monetary numbers."""
    context: dict[str, Any] = {}
    for name, value in row.items():
        if len(name) > 128:
            raise ValueError(
                "Record field names must be at most 128 characters."
            )
        expected = properties.get(name, {}).get("type")
        context[name] = _scalar(name, value, expected)
    return context


def _evaluate(rule: _Rule, context: dict[str, Any], index: int) -> Any:
    """Run one rule on one row's context; it must return a boolean."""
    try:
        result = rule.program.evaluate(context)
        if not isinstance(result, (bool, celtypes.BoolType)):
            raise ValueError("Predicate did not return a boolean.")
    except Exception as exc:
        raise ValueError(
            f"Rule {rule.identifier}, row {index}: evaluation failed ({type(exc).__name__})."
        ) from None
    return result


class CustomRuleScheme:
    """A policy instance scoped to one caller, never stored in a singleton.

    Args:
        source: Inline YAML containing the complete policy.

    Attributes:
        meta: Plugin metadata; the instance is not globally registered.
    """

    meta = PluginMeta(
        "custom", VERSION, "Apply bounded, deterministic CEL policy rules."
    )

    def __init__(self, source: str) -> None:
        self._rules = _load_rules(source)
        self._fields = frozenset(
            name for rule in self._rules for name in rule.fields
        )

    def _context(
        self, index: int, row: dict[str, Any], properties: dict[str, Any]
    ) -> dict[str, Any]:
        """The CEL activation for one row: the fields the rules read."""
        try:
            return _activation(
                {name: row[name] for name in self._fields if name in row},
                properties,
            )
        except (
            ValueError,
            TypeError,
            InvalidOperation,
            OverflowError,
        ) as exc:
            raise ValueError(
                f"Policy row {index}: invalid scalar input ({type(exc).__name__})."
            ) from None

    def validate(
        self, rows: list[dict[str, Any]], *, message_type: str
    ) -> SchemeResult:
        """Return structured findings for rules whose predicates are true.

        Invalid inputs and failed expression evaluations propagate
        ValueError, naming the row and, for an evaluation, the rule.

        Args:
            rows: Flat payment records, never mutated.
            message_type: Bundled schema used for numeric coercion.

        Returns:
            Findings in row and policy order; warnings do not reject a batch.
        """
        properties = SchemaValidator(message_type).schema["properties"]
        findings: list[SchemeFinding] = []
        for index, row in enumerate(rows):
            context = self._context(index, row, properties)
            findings.extend(
                SchemeFinding(
                    index, None, rule.identifier, rule.severity, rule.message
                )
                for rule in self._rules
                if _evaluate(rule, context, index)
            )
        return SchemeResult(
            not any(f.severity == "error" for f in findings), findings
        )


def validate_policy(
    rows: list[dict[str, Any]],
    source: str,
    profile: str | None = None,
    message_type: str = "pain.001.001.03",
) -> SchemeValidationResult:
    """Compose a private policy with the requested built-in scheme profiles.

    Invalid policies, profiles or record evaluations propagate ValueError
    from the policy or scheme implementation.

    Args:
        rows: Flat payment records.
        source: Inline YAML rules, never a server-side file path.
        profile: Optional comma-separated scheme names, including custom.
        message_type: The bundled message schema to validate against.

    Returns:
        The combined findings in stable row order.

    """
    policy = CustomRuleScheme(source)
    names = list(
        dict.fromkeys(
            name.strip() for name in (profile or "").split(",") if name.strip()
        )
    )
    builtins = [name for name in names if name != "custom"]
    combined = (
        validate_scheme(rows, ",".join(builtins), message_type=message_type)
        if builtins
        else SchemeValidationResult("custom")
    )
    custom = policy.validate(rows, message_type=message_type)
    combined.profile = ",".join([*builtins, "custom"])
    combined.violations.extend(
        SchemeViolation(f.rule, f.message, f.row_index, f.field, f.severity)
        for f in custom.findings
    )
    combined.violations.sort(key=lambda violation: violation.index)
    return combined
