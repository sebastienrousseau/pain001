# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Pin the identifier checks' exact message, defaults and IBAN call.

The broader suite checked that a bad IBAN is refused but matched the
refusal with a regex, never called ``identifier_errors`` or
``load_batch`` with their defaults, and never looked at how
``validate_iban`` is called. These tests compare the whole message,
use each default, and spy on the IBAN validator, so the mutation
run's survivors in ``_reason``, ``identifier_errors``,
``check_identifiers`` and ``load_batch`` are killed directly.
"""

from __future__ import annotations

import csv
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.exceptions import PaymentValidationError
from pain001.validation import _identifiers
from pain001.validation._identifiers import (
    _reason,
    check_identifiers,
    identifier_errors,
)
from pain001.validation._one_batch import load_batch

_BAD_IBAN = "DE89370400440532013001"
_GOOD_IBAN = "DE89370400440532013000"
_IBAN_REASON = (
    "not a valid IBAN (IBAN checksum validation failed "
    "(mod 97 = 28, expected 1))"
)
_TYPE = "pain.001.001.03"


def test_reason_calls_validate_iban_non_strict(monkeypatch):
    """``_reason`` asks for the tuple form: ``strict`` is exactly False."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def spy(value: str, **kwargs: Any) -> tuple[bool, str | None]:
        calls.append((value, kwargs))
        return True, None

    monkeypatch.setattr(_identifiers, "validate_iban", spy)
    assert _reason("IBAN", _GOOD_IBAN) is None
    assert calls == [(_GOOD_IBAN, {"strict": False})]
    assert calls[0][1]["strict"] is False


def test_reason_names_a_bad_iban_without_raising():
    """A bad IBAN yields its reason; a good one yields ``None``."""
    assert _reason("IBAN", _BAD_IBAN) == _IBAN_REASON
    assert _reason("IBAN", _GOOD_IBAN) is None


def test_identifier_errors_counts_rows_from_zero_by_default():
    """Without ``start`` the first row is index 0."""
    rows = [{"debtor_account_IBAN": _BAD_IBAN}]
    assert identifier_errors(rows) == [
        (0, "debtor_account_IBAN", _IBAN_REASON)
    ]


def test_identifier_errors_honours_start():
    """``start`` offsets the index of a chunk."""
    rows = [
        {"debtor_account_IBAN": _GOOD_IBAN},
        {"debtor_account_IBAN": _BAD_IBAN},
    ]
    assert identifier_errors(rows, start=5) == [
        (6, "debtor_account_IBAN", _IBAN_REASON)
    ]


def test_check_identifiers_message_is_exact():
    """The refusal reads exactly as documented, opt-out hint included."""
    with pytest.raises(PaymentValidationError) as caught:
        check_identifiers([{"debtor_account_IBAN": _BAD_IBAN}])
    assert str(caught.value) == (
        "Invalid identifiers (1):\n"
        f"  line 1, column debtor_account_IBAN: {_IBAN_REASON} (P001-E020)\n"
        "Fix the values, or skip these checks with --no-identifier-checks "
        "(identifier_checks=False)."
    )
    assert caught.value.field == "debtor_account_IBAN"


def test_check_identifiers_passes_clean_rows():
    """Valid identifiers raise nothing."""
    check_identifiers([{"debtor_account_IBAN": _GOOD_IBAN}])


def _template_rows() -> list[dict[str, Any]]:
    path = TEMPLATES_DIR / _TYPE / "template.csv"
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _rows_with_bad_iban() -> list[dict[str, Any]]:
    rows = _template_rows()
    for row in rows:
        row["debtor_account_IBAN"] = _BAD_IBAN
    return rows


def test_load_batch_checks_identifiers_by_default():
    """``load_batch`` runs the identifier checks unless told not to."""
    with pytest.raises(PaymentValidationError) as caught:
        load_batch(_rows_with_bad_iban(), _TYPE)
    assert str(caught.value).startswith("Invalid identifiers (")


def test_load_batch_skips_identifier_checks_on_request():
    """``identifier_checks=False`` lets the same rows load."""
    rows = load_batch(_rows_with_bad_iban(), _TYPE, identifier_checks=False)
    assert rows
    assert {row["debtor_account_IBAN"] for row in rows} == {_BAD_IBAN}
