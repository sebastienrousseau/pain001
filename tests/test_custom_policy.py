# SPDX-License-Identifier: Apache-2.0 OR MIT
"""CEL policy safety, exact amounts, calendars and scheme composition."""

from copy import deepcopy
from decimal import Decimal

import pytest
import yaml

pytest.importorskip("celpy")
pytest.importorskip("holidays")

from pain001.plugins import AbstractScheme  # noqa: E402
from pain001.validation import policy  # noqa: E402

TYPE = "pain.001.001.03"


def source(where="payment_amount > 50000", severity="error", **overrides):
    """Build a small policy while preserving YAML string types."""
    spec = {
        "id": "LIMIT",
        "where": where,
        "severity": severity,
        "message": "Payment requires review.",
    }
    spec.update(overrides)
    return yaml.safe_dump([spec])


def test_friday_acceptance_and_no_mutation():
    """The requested Friday predicate rejects only matching records."""
    rules = source(
        'payment_amount > 50000 && day_of_week(requested_execution_date) == "Friday"'
    )
    rows = [
        {
            "payment_amount": "50000.01",
            "requested_execution_date": "2026-09-25",
            "ctrl_sum": "",
        },
        {"payment_amount": "50000", "requested_execution_date": "2026-09-25"},
        {"payment_amount": "60000", "requested_execution_date": "2026-09-24"},
    ]
    before = deepcopy(rows)
    scheme = policy.CustomRuleScheme(rules)
    assert isinstance(scheme, AbstractScheme)
    result = scheme.validate(rows, message_type=TYPE)
    assert not result.is_valid
    assert [(f.row_index, f.rule) for f in result.findings] == [(0, "LIMIT")]
    assert rows == before


def test_exact_decimal_boundaries():
    """Monetary comparisons and literals do not round through binary floats."""
    scheme = policy.CustomRuleScheme(
        source('payment_amount == decimal("50000.01")')
    )
    assert not scheme.validate(
        [{"payment_amount": "50000.01"}], message_type=TYPE
    ).is_valid
    assert scheme.validate(
        [{"payment_amount": "50000.01000000000001"}], message_type=TYPE
    ).is_valid


@pytest.mark.parametrize("severity", ["warning", "info"])
def test_nonblocking_severities(severity):
    """Warnings and information are reported without invalidating a batch."""
    result = policy.validate_policy(
        [{"payment_amount": 60000}], source(severity=severity)
    )
    assert result.is_valid
    assert result.violations[0].severity == severity


def test_request_local_rules_do_not_leak():
    """A policy invocation does not register or mutate a global scheme."""
    rows = [{"payment_amount": 60000}]
    assert not policy.validate_policy(rows, source()).is_valid
    assert policy.validate_policy(rows, source("false")).is_valid


def test_scheme_composition():
    """Custom and existing scheme findings are combined deterministically."""
    rows = [{"payment_amount": "60000", "currency": "USD"}]
    result = policy.validate_policy(
        rows, source(), "sepa-sct,custom,sepa-sct", TYPE
    )
    assert result.profile == "sepa-sct,custom"
    assert "LIMIT" in {v.rule for v in result.violations}
    assert "SEPA-CCY" in {v.rule for v in result.violations}
    with pytest.raises(ValueError, match="Unknown scheme"):
        policy.validate_policy(rows, source(), "unknown")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{}",
        "[]",
        "- true",
        "[",
        "- &x {}\n- *x",
        "!!python/object:builtins.object {}",
        "x" * 65537,
    ],
)
def test_invalid_yaml(text):
    """Malformed YAML, tags, anchors and oversized policies are refused."""
    with pytest.raises(ValueError):
        policy.CustomRuleScheme(text)


def test_rule_limit_and_duplicate_ids():
    """Rule counts and IDs are bounded before evaluation."""
    spec = yaml.safe_load(source())[0]
    for specs in ([deepcopy(spec) for _ in range(65)], [spec, deepcopy(spec)]):
        with pytest.raises(ValueError):
            policy.CustomRuleScheme(yaml.safe_dump(specs))


@pytest.mark.parametrize(
    "changes",
    [
        {"id": None},
        {"id": "lowercase"},
        {"id": "X" * 65},
        {"where": True},
        {"where": ""},
        {"where": "x" * 2049},
        {"severity": "fatal"},
        {"message": None},
        {"message": ""},
        {"message": "x" * 1025},
    ],
)
def test_invalid_rule_fields(changes):
    """Rule metadata is typed and bounded, with no implicit YAML coercion."""
    with pytest.raises(ValueError):
        policy.CustomRuleScheme(source(**changes))


@pytest.mark.parametrize(
    "where",
    [
        "payment_amount >",
        '__import__("os")',
        'currency_of_iban(debtor_account_IBAN) == "EUR"',
        "[1,2,3].all(x, x > 0)",
        "payment_amount > 1.01",
        " + ".join(["1"] * 150),
    ],
)
def test_invalid_or_forbidden_expressions_identify_rule(where):
    """Syntax errors, arbitrary calls, macros and floats fail at load time."""
    with pytest.raises(ValueError, match="Rule LIMIT:"):
        policy.CustomRuleScheme(source(where))


@pytest.mark.parametrize(
    "where", ["missing > 1", 'decimal("NaN") > 1', "1", "1 / 0 > 2"]
)
def test_evaluation_errors_fail_closed(where):
    """Missing inputs and nonboolean predicates cannot silently pass."""
    with pytest.raises(
        ValueError, match="Rule LIMIT, row 0: evaluation failed"
    ):
        policy.validate_policy([{}], source(where))


def test_bounded_string_methods():
    """Useful scalar string checks remain available without collection loops."""
    assert not policy.validate_policy(
        [{"initiator_name": "Acme"}], source('initiator_name.startsWith("A")')
    ).is_valid


def test_calendar_helpers():
    """Country calendars distinguish weekdays, weekends and public holidays."""
    assert str(policy.day_of_week("2026-09-25")) == "Friday"
    assert str(policy.country_of_iban("DE89370400440532013000")) == "DE"
    assert str(policy.country_of_iban(" de89 3704 0044 0532 0130 00")) == "DE"
    assert policy.is_business_day("2026-09-25", "DE")
    assert not policy.is_business_day("2026-09-26", "DE")
    assert not policy.is_business_day("2026-12-25", "DE")
    for value in ("25/09/2026", "2026-02-31"):
        with pytest.raises(ValueError):
            policy.day_of_week(value)
    with pytest.raises(ValueError, match="valid IBAN"):
        policy.country_of_iban("invalid")
    with pytest.raises(ValueError, match="1900"):
        policy.is_business_day("1800-01-01", "DE")
    with pytest.raises(NotImplementedError):
        policy.is_business_day("2026-09-25", "XX")


@pytest.mark.parametrize("value", [3, "x" * 65, "Infinity", "NaN"])
def test_decimal_rejects_nonfinite_or_nonstring_values(value):
    """The decimal helper cannot introduce infinities or inexact arguments."""
    with pytest.raises(ValueError):
        policy.decimal(value)


def test_scalar_context_types():
    """Typed context supports flags, counts, exact numbers, text and null."""
    row = {
        "flag": True,
        "nb_of_txs": "3",
        "count": 2,
        "rate": 1.25,
        "precise": Decimal("2.30"),
        "name": "Acme",
        "missing": None,
    }
    properties = {"nb_of_txs": {"type": "integer"}}
    context = policy._activation(row, properties)
    assert context["flag"] is not None and bool(context["flag"])
    assert context["nb_of_txs"] == 3
    assert context["rate"] == Decimal("1.25")
    assert context["precise"] == Decimal("2.30")
    assert context["missing"] is None


@pytest.mark.parametrize(
    "row",
    [
        {"x" * 129: 1},
        {"name": "x" * 4097},
        {"nested": []},
        {"payment_amount": "not a number"},
    ],
)
def test_invalid_context_values(row):
    """Nested, oversized or malformed numeric input cannot enter CEL."""
    with pytest.raises((ValueError, ArithmeticError)):
        policy._activation(row, {})


def test_invalid_record_reports_index_without_value():
    """Payment values are not echoed in runtime diagnostics."""
    with pytest.raises(
        ValueError, match="Policy row 0: invalid scalar input"
    ) as caught:
        policy.validate_policy(
            [{"payment_amount": "sensitive-invalid-value"}], source()
        )
    assert "sensitive-invalid-value" not in str(caught.value)


def test_unsupported_message_type():
    """Policy schemas remain confined to bundled message types."""
    with pytest.raises(ValueError, match="Invalid message type"):
        policy.validate_policy([], source(), message_type="unknown")
