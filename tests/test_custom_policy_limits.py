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

"""Custom policy limits at their exact bounds, and the refusals' wording.

``tests/test_custom_policy.py`` proves each bound refuses what lies
beyond it; this module proves each bound is inclusive (the largest
allowed policy, rule, expression, message and input still load) and
pins the message every refusal gives, which is what a policy author
reads on the CLI, REST and MCP surfaces.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
import yaml

from pain001.validation import policy

TYPE = "pain.001.001.03"


def _spec(**overrides: Any) -> dict[str, Any]:
    """One rule spec, with overrides."""
    spec: dict[str, Any] = {
        "id": "LIMIT",
        "where": 'name == "x"',
        "severity": "error",
        "message": "Review.",
    }
    spec.update(overrides)
    return spec


def _source(**overrides: Any) -> str:
    """A one-rule policy, with overrides."""
    return yaml.safe_dump([_spec(**overrides)])


def _refusal(source: str) -> str:
    """The message a policy is refused with."""
    with pytest.raises(ValueError) as caught:
        policy.CustomRuleScheme(source)
    return str(caught.value)


def test_a_policy_of_exactly_64_kib_loads() -> None:
    """The size limit is inclusive; one byte more is refused by name."""
    base = _source()
    padded = (
        base + "#" + "x" * (policy.MAX_POLICY_BYTES - len(base) - 2) + "\n"
    )
    assert len(padded.encode("utf-8")) == policy.MAX_POLICY_BYTES
    policy.CustomRuleScheme(padded)
    assert _refusal(padded + "#") == "Policy exceeds the 64 KiB limit."


def test_a_policy_of_64_rules_loads() -> None:
    """Sixty-four rules is the most; sixty-five is refused by name."""
    specs = [_spec(id=f"R{i}") for i in range(64)]
    assert len(policy.CustomRuleScheme(yaml.safe_dump(specs))._rules) == 64
    specs.append(_spec(id="R64"))
    assert (
        _refusal(yaml.safe_dump(specs))
        == "A policy must contain between 1 and 64 rules."
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "- &x {}\n- *x",
            "YAML aliases, anchors and explicit tags are not allowed in "
            "policies.",
        ),
        ("[", "Invalid policy YAML."),
        (
            "- {id: X}",
            "Each rule requires exactly id, where, severity and message.",
        ),
        (
            yaml.safe_dump([_spec(), _spec()]),
            "Rule IDs must be unique uppercase identifiers of at most 64 "
            "characters.",
        ),
    ],
)
def test_policy_shape_refusals(source: str, message: str) -> None:
    """Forbidden YAML, bad YAML, bad keys and duplicate ids say why."""
    assert _refusal(source) == message


def test_rule_field_bounds_are_inclusive() -> None:
    """A 2048-character where and 1- and 1024-character messages load."""
    where = 'name == "' + "x" * 2038 + '"'
    assert len(where) == 2048
    policy.CustomRuleScheme(_source(where=where))
    policy.CustomRuleScheme(_source(message="R"))
    policy.CustomRuleScheme(_source(message="R" * 1024))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"where": 'name == "' + "x" * 2039 + '"'},
            "where must be a CEL string of 1 through 2048 characters.",
        ),
        ({"severity": "fatal"}, "severity must be error, warning or info."),
        (
            {"message": "R" * 1025},
            "message must be a string of 1 through 1024 characters.",
        ),
        (
            {"where": 'currency_of_iban(iban) == "EUR"'},
            "An IBAN does not encode account currency; use the record's "
            "currency field.",
        ),
        ({"where": "foo(name)"}, "Function 'foo' is not allowed."),
        (
            {"where": "[1, 2].all(x, x > 0)"},
            "Only bounded string methods are allowed; CEL collection macros "
            "are disabled.",
        ),
        (
            {"where": "amount > 1.5"},
            'Use decimal("1.23") instead of a floating-point literal.',
        ),
    ],
)
def test_rule_refusals_name_the_rule_and_the_reason(
    overrides: dict[str, Any], message: str
) -> None:
    """Each rule-level refusal is prefixed with the rule id."""
    assert _refusal(_source(**overrides)) == f"Rule LIMIT: {message}"


def test_the_expression_node_limit_is_512() -> None:
    """A 512-node expression loads; 513 nodes is refused by name."""
    terms = " || ".join(["a"] * 55)
    policy.CustomRuleScheme(_source(where=f"{terms} || a + a"))
    assert _refusal(_source(where=f"{terms} || !!!!a")) == (
        "Rule LIMIT: Expression exceeds the 512-node limit."
    )


def test_findings_carry_the_rule_message() -> None:
    """Both the plugin result and the composed result keep the message."""
    scheme = policy.CustomRuleScheme(_source())
    result = scheme.validate([{"name": "x"}], message_type=TYPE)
    assert [
        (f.row_index, f.rule, f.severity, f.message) for f in result.findings
    ] == [(0, "LIMIT", "error", "Review.")]
    combined = policy.validate_policy([{"name": "x"}], _source())
    assert combined.profile == "custom"
    assert [
        (v.rule, v.message, v.index, v.field) for v in combined.violations
    ] == [("LIMIT", "Review.", 0, None)]


def test_policy_composes_two_builtin_profiles() -> None:
    """Built-in names are joined back with commas and custom goes last."""
    row = {
        "payment_currency": "USD",
        "creditor_account_IBAN": "DE89370400440532013000",
        "payment_amount": "5",
        "requested_execution_date": "2026-01-02",
        "name": "x",
    }
    result = policy.validate_policy(
        [row, row], _source(), "sepa-sct, anti-duplicate,custom"
    )
    assert result.profile == "sepa-sct,anti-duplicate,custom"
    rules = {v.rule for v in result.violations}
    assert {"SEPA-CCY", "DUP-CREDITOR-DATE", "LIMIT"} <= rules


def _value_error(call: Any, *args: Any) -> str:
    """The message ``call(*args)`` raises ValueError with."""
    with pytest.raises(ValueError) as caught:
        call(*args)
    return str(caught.value)


def test_calendar_helper_messages_and_year_bounds() -> None:
    """Dates must be ISO; calendars cover 1900 through 2100 inclusive."""
    assert (
        _value_error(policy.day_of_week, "25/09/2026")
        == "Use ISO dates in YYYY-MM-DD format."
    )
    assert not policy.is_business_day("1900-12-25", "GB")
    assert policy.is_business_day("1900-01-02", "GB")
    assert not policy.is_business_day("2100-12-27", "GB")
    assert policy.is_business_day("2100-12-29", "GB")
    for value in ("1899-12-29", "2101-01-03"):
        assert (
            _value_error(policy.is_business_day, value, "GB")
            == "Business-day calendars support years 1900 through 2100."
        )


def test_country_of_iban_accepts_grouping_and_names_its_refusal() -> None:
    """Spaces and hyphens are grouping; anything invalid is refused."""
    assert str(policy.country_of_iban("DE89-3704-0044-0532-0130-00")) == "DE"
    assert (
        _value_error(policy.country_of_iban, "DE00")
        == "country_of_iban requires a valid IBAN."
    )


def test_decimal_helper_bounds_and_messages() -> None:
    """Up to 64 characters is accepted; longer or infinite is refused."""
    assert policy.decimal("1" * 64) == Decimal("1" * 64)
    assert (
        _value_error(policy.decimal, "1" * 65)
        == "decimal() requires a short decimal string."
    )
    assert (
        _value_error(policy.decimal, "Infinity")
        == "Policy numbers must be finite."
    )


def test_scalar_input_bounds_and_messages() -> None:
    """Strings to 4096 and names to 128 characters enter; more do not."""
    assert str(policy._string("s" * 4096)) == "s" * 4096
    assert (
        _value_error(policy._string, "s" * 4097)
        == "Policy string inputs must be at most 4096 characters."
    )
    assert policy._scalar("rate", "1.50", "number") == Decimal("1.50")
    assert (
        _value_error(policy._scalar, "nested", [], None)
        == "Policy inputs must be flat scalar records."
    )
    name = "n" * 128
    assert policy._activation({name: "v"}, {}) == {name: "v"}
    assert (
        _value_error(policy._activation, {"n" * 129: "v"}, {})
        == "Record field names must be at most 128 characters."
    )


def test_runtime_failures_name_the_exception_type() -> None:
    """Evaluation and input failures name the error class, not the value."""
    scheme = policy.CustomRuleScheme(_source(where="name"))
    with pytest.raises(ValueError) as caught:
        scheme.validate([{"name": "x"}], message_type=TYPE)
    assert str(caught.value) == (
        "Rule LIMIT, row 0: evaluation failed (ValueError)."
    )
    with pytest.raises(ValueError) as caught:
        scheme.validate([{"name": "x" * 4097}], message_type=TYPE)
    assert str(caught.value) == (
        "Policy row 0: invalid scalar input (ValueError)."
    )
