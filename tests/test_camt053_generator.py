# Copyright (C) 2023-2026 Pain001. All rights reserved.
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

"""Tests for the camt.053 statement generator (and round-trip)."""

import pytest

from pain001.camt053 import (
    build_camt053_statement,
    parse_camt053_statement,
)

IBAN = "DE89370400440532013000"


def _write(tmp_path, xml: str) -> str:
    """Write an XML string to a temp file and return its path.

    Args:
        tmp_path: pytest tmp_path fixture.
        xml: The XML string.

    Returns:
        The path to the written file.
    """
    path = tmp_path / "stmt.xml"
    path.write_text(xml, encoding="utf-8")
    return str(path)


class TestBuildCamt053:
    """Structure and validation of the generator output."""

    def test_minimal_statement(self) -> None:
        """A statement with no entries is well-formed."""
        xml = build_camt053_statement("STMT-1", IBAN, "EUR", [])
        assert xml.startswith("<?xml")
        assert "BkToCstmrStmt" in xml
        assert "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02" in xml

    def test_missing_amount_rejected(self) -> None:
        """An entry without an amount raises ValueError."""
        with pytest.raises(ValueError, match="amount"):
            build_camt053_statement(
                "S", IBAN, "EUR", [{"credit_debit_indicator": "CRDT"}]
            )

    def test_invalid_indicator_rejected(self) -> None:
        """An invalid credit/debit indicator raises ValueError."""
        with pytest.raises(ValueError, match="credit/debit"):
            build_camt053_statement(
                "S",
                IBAN,
                "EUR",
                [{"amount": "1.00", "credit_debit_indicator": "XX"}],
            )

    def test_invalid_status_rejected(self) -> None:
        """An invalid entry status raises ValueError."""
        with pytest.raises(ValueError, match="entry status"):
            build_camt053_statement(
                "S",
                IBAN,
                "EUR",
                [
                    {
                        "amount": "1.00",
                        "credit_debit_indicator": "CRDT",
                        "status": "NOPE",
                    }
                ],
            )

    def test_per_entry_currency_override(self) -> None:
        """An entry may override the account currency."""
        xml = build_camt053_statement(
            "S",
            IBAN,
            "EUR",
            [
                {
                    "amount": "1.00",
                    "credit_debit_indicator": "CRDT",
                    "currency": "USD",
                }
            ],
        )
        assert 'Ccy="USD"' in xml


class TestRoundTrip:
    """Generated statements parse back to the same data."""

    def test_full_entry_round_trip(self, tmp_path) -> None:
        """A fully-populated entry survives generate→parse."""
        xml = build_camt053_statement(
            "STMT-1",
            IBAN,
            "EUR",
            [
                {
                    "credit_debit_indicator": "CRDT",
                    "status": "BOOK",
                    "amount": "150.00",
                    "booking_date": "2026-04-10",
                    "value_date": "2026-04-11",
                    "entry_reference": "ENTRY-001",
                    "remittance_information": "Invoice 42",
                }
            ],
            electronic_sequence_number="7",
        )
        parsed = parse_camt053_statement(_write(tmp_path, xml))
        assert parsed["statement_id"] == "STMT-1"
        assert parsed["electronic_sequence_number"] == "7"
        assert parsed["iban"] == IBAN
        entry = parsed["entries"][0]
        assert entry["credit_debit_indicator"] == "CRDT"
        assert entry["amount"] == "150.00"
        assert entry["currency"] == "EUR"
        assert entry["booking_date"] == "2026-04-10"
        assert entry["value_date"] == "2026-04-11"
        assert entry["entry_reference"] == "ENTRY-001"
        assert entry["remittance_information"] == "Invoice 42"

    def test_minimal_entry_round_trip(self, tmp_path) -> None:
        """An entry with only required fields parses (optionals omitted)."""
        xml = build_camt053_statement(
            "STMT-2",
            IBAN,
            "EUR",
            [{"amount": "9.99", "credit_debit_indicator": "DBIT"}],
        )
        assert "NtryDtls" not in xml  # no remittance block
        parsed = parse_camt053_statement(_write(tmp_path, xml))
        entry = parsed["entries"][0]
        assert entry["credit_debit_indicator"] == "DBIT"
        assert entry["amount"] == "9.99"
        assert entry["booking_date"] == ""

    def test_top_level_export(self) -> None:
        """build_camt053_statement is exposed at the package top level."""
        from pain001 import build_camt053_statement as top

        assert top("S", IBAN, "EUR", []).startswith("<?xml")
