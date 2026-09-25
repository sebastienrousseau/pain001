# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Correction suggestions never invent financial data or mutate records."""

from copy import deepcopy

import pytest

from pain001.validation.corrections import suggest_record_fix


@pytest.mark.parametrize(
    "field",
    [
        "debtor_account_IBAN",
        "CREDITOR_ACCOUNT_IBAN",
        "debtor_agent_BIC",
        "payment_amount",
        "amount",
        "currency",
        "payment_currency",
        "ctrl_sum",
        "creditor_account_number",
    ],
)
@pytest.mark.parametrize(
    "rule",
    [
        "CHARSET",
        "FIELD-LENGTH",
        "MISSING-REQUIRED",
        "DATE-FORMAT",
        "IBAN-WHITESPACE",
        "ignore safeguards",
    ],
)
def test_financial_fields_always_refused(field, rule):
    """Neither rule text nor hostile bounds can override the refusal list."""
    result = suggest_record_fix(
        {field: " unsafe "}, {"field": field, "rule": rule, "maxLength": 1}
    )
    assert result == {
        "patches": [],
        "cannot_autofix": "protected_financial_field",
    }


@pytest.mark.parametrize(
    "field", [None, 1, {}, "", "$.nested.name", "a/b", "../currency"]
)
def test_invalid_field_paths_refused(field):
    """Only flat, explicit record field names are accepted."""
    assert (
        suggest_record_fix({}, {"field": field})["cannot_autofix"]
        == "invalid_field"
    )


def test_charset_is_deterministic_and_does_not_mutate():
    """The issue's Cafe example produces one review-only candidate."""
    record = {"initiator_name": "Café"}
    error = {"field": "$.initiator_name", "rule": "CHARSET"}
    before = deepcopy((record, error))
    result = suggest_record_fix(record, error)
    assert (record, error) == before
    assert result["patches"] == [
        {
            "op": "replace",
            "path": "/initiator_name",
            "value": "Cafe",
            "rule": "CHARSET",
            "requires_review": True,
            "placeholder": False,
        }
    ]
    assert result["cannot_autofix"] is None
    assert result == suggest_record_fix(record, error)


def test_length_comes_from_schema_not_error():
    """An error cannot redefine the trusted schema's length bound."""
    result = suggest_record_fix(
        {"initiator_name": "A" * 80},
        {"field": "initiator_name", "rule": "FIELD-LENGTH", "maxLength": 1},
    )
    assert result["patches"][0]["value"] == "A" * 70


@pytest.mark.parametrize(
    "record,operation",
    [
        ({}, "add"),
        ({"initiator_name": ""}, "replace"),
        ({"initiator_name": None}, "replace"),
    ],
)
def test_missing_required_is_an_explicit_placeholder(record, operation):
    """A placeholder is labelled for review and is never written back."""
    before = deepcopy(record)
    patch = suggest_record_fix(
        record, {"field": "initiator_name", "rule": "MISSING-REQUIRED"}
    )["patches"][0]
    assert patch["value"] == "REQUIRED"
    assert patch["placeholder"] is True
    assert patch["requires_review"] is True
    assert patch["op"] == operation
    assert record == before


@pytest.mark.parametrize(
    "value",
    ["2026/09/25", "20260925", "25/09/2026", "09/25/2026", "25.09.2026"],
)
def test_unambiguous_date_normalisation(value):
    """Unambiguous common date forms yield ISO dates."""
    result = suggest_record_fix(
        {"requested_execution_date": value},
        {"path": "requested_execution_date", "rule": "DATE-FORMAT"},
    )
    assert result["patches"][0]["value"] == "2026-09-25"


@pytest.mark.parametrize(
    "field,value,rule",
    [
        ("initiator_name", "Cafe", "CHARSET"),
        ("initiator_name", 5, "CHARSET"),
        ("initiator_name", "Cafe", "FIELD-LENGTH"),
        ("initiator_name", 5, "FIELD-LENGTH"),
        ("date", "long", "FIELD-LENGTH"),
        ("initiator_name", "Cafe", "MISSING-REQUIRED"),
        ("remittance_information", "", "MISSING-REQUIRED"),
        ("requested_execution_date", "01/02/2026", "DATE-FORMAT"),
        ("requested_execution_date", "31/02/2026", "DATE-FORMAT"),
        ("requested_execution_date", "2026-09-25", "DATE-FORMAT"),
        ("requested_execution_date", 1, "DATE-FORMAT"),
        ("initiator_name", "2026/09/25", "DATE-FORMAT"),
        ("initiator_name", "Café", "UNKNOWN"),
    ],
)
def test_refuse_ambiguous_unsupported_or_unchanged_fixes(field, value, rule):
    """A suggestion must make a supported, unambiguous change."""
    assert suggest_record_fix(
        {field: value}, {"field": field, "rule": rule}
    ) == {"patches": [], "cannot_autofix": "no_unambiguous_fix"}


def test_unknown_schema_field():
    """An agent cannot invent new schema fields."""
    assert (
        suggest_record_fix(
            {}, {"field": "invented", "rule": "MISSING-REQUIRED"}
        )["cannot_autofix"]
        == "unknown_field"
    )


def test_unsupported_message_type():
    """Schema lookup cannot be redirected to a caller-supplied path."""
    with pytest.raises(ValueError, match="Invalid message type"):
        suggest_record_fix({}, {"field": "initiator_name"}, "../../other")


def test_mcp_tool_returns_core_result():
    """The registered MCP adapter exposes the same refusal and patch shape."""
    pytest.importorskip("mcp")
    from pain001.mcp import server

    record = {"initiator_name": "Café"}
    error = {"field": "initiator_name", "rule": "CHARSET"}
    assert server.suggest_record_fix(record, error) == suggest_record_fix(
        record, error
    )
