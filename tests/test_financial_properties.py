# Copyright (C) 2023-2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Property-based tests for financial amount handling.

These properties pin down the financial-correctness invariants:
amounts are exact two-decimal strings, totals are exact Decimal sums,
and anything ambiguous is rejected rather than silently rounded.
"""

import re
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pain001.exceptions import PaymentValidationError
from pain001.xml.generate_xml import (
    _format_amount,
    _normalize_financial_fields,
)

TWO_DP = re.compile(r"^\d+\.\d{2}$")

valid_amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


class TestFormatAmountProperties:
    @given(amount=valid_amounts)
    @settings(max_examples=200, deadline=None)
    def test_valid_amounts_round_trip_exactly(self, amount):
        formatted = _format_amount(amount, 1)
        assert TWO_DP.match(formatted)
        assert Decimal(formatted) == amount

    @given(amount=valid_amounts)
    @settings(max_examples=100, deadline=None)
    def test_string_input_equivalent_to_decimal_input(self, amount):
        assert _format_amount(str(amount), 1) == _format_amount(amount, 1)

    @given(
        amount=st.decimals(
            min_value=Decimal("0.001"),
            max_value=Decimal("1000000"),
            places=3,
            allow_nan=False,
            allow_infinity=False,
        ).filter(lambda d: d != d.quantize(Decimal("0.01")))
    )
    @settings(max_examples=100, deadline=None)
    def test_more_than_two_decimals_rejected(self, amount):
        with pytest.raises(PaymentValidationError):
            _format_amount(amount, 1)

    @given(
        amount=st.decimals(
            max_value=Decimal("0.00"),
            min_value=Decimal("-999999999"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_non_positive_rejected(self, amount):
        with pytest.raises(PaymentValidationError):
            _format_amount(amount, 1)

    @pytest.mark.parametrize(
        "bad", [None, "", "   ", "abc", "12,50", "NaN", "Infinity", "1e"]
    )
    def test_non_numeric_and_missing_rejected(self, bad):
        with pytest.raises(PaymentValidationError):
            _format_amount(bad, 1)


class TestNormalizeFinancialFieldsProperties:
    @given(amounts=st.lists(valid_amounts, min_size=1, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_ctrl_sum_is_exact_decimal_sum(self, amounts):
        rows = [{"payment_amount": a} for a in amounts]
        normalized, nb_of_txs, ctrl_sum = _normalize_financial_fields(rows)

        assert nb_of_txs == str(len(amounts))
        assert Decimal(ctrl_sum) == sum(amounts)
        for row, original in zip(normalized, amounts):
            assert Decimal(row["payment_amount"]) == original

    @given(amounts=st.lists(valid_amounts, min_size=1, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_input_rows_not_mutated(self, amounts):
        rows = [{"payment_amount": a} for a in amounts]
        snapshots = [dict(r) for r in rows]
        _normalize_financial_fields(rows)
        assert rows == snapshots

    def test_one_bad_row_fails_whole_batch(self):
        rows = [
            {"payment_amount": "10.00"},
            {"payment_amount": "0.005"},
        ]
        with pytest.raises(PaymentValidationError):
            _normalize_financial_fields(rows)
