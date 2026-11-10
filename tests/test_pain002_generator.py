# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Tests for the pain.002 status-report generator (and round-trip)."""

import pytest

from pain001.pain002 import (
    build_pain002_report,
    parse_pain002_report,
)


def _write(tmp_path, xml: str):
    """Write an XML string to a temp file and return its path.

    Args:
        tmp_path: pytest tmp_path fixture.
        xml: The XML string.

    Returns:
        The path to the written file.
    """
    path = tmp_path / "report.xml"
    path.write_text(xml, encoding="utf-8")
    return str(path)


class TestBuildPain002:
    """Structure and validation of the generator output."""

    def test_minimal_report_is_wellformed(self) -> None:
        """A minimal report contains the document and report elements."""
        xml = build_pain002_report(
            message_id="STS-1",
            original_message_id="MSG-1",
            group_status="ACCP",
            payment_statuses=[],
        )
        assert xml.startswith("<?xml")
        assert "CstmrPmtStsRpt" in xml
        assert "urn:iso:std:iso:20022:tech:xsd:pain.002.001.03" in xml

    def test_invalid_group_status_rejected(self) -> None:
        """An unknown group status code raises ValueError."""
        with pytest.raises(ValueError, match="group status"):
            build_pain002_report(
                message_id="x",
                original_message_id="y",
                group_status="NOPE",
                payment_statuses=[],
            )

    def test_invalid_payment_status_rejected(self) -> None:
        """An unknown payment status code raises ValueError."""
        with pytest.raises(ValueError, match="payment status"):
            build_pain002_report(
                "x",
                "y",
                "ACCP",
                [
                    {
                        "original_payment_information_id": "p",
                        "payment_information_status": "BAD",
                    }
                ],
            )

    def test_invalid_transaction_status_rejected(self) -> None:
        """An unknown transaction status code raises ValueError."""
        with pytest.raises(ValueError, match="transaction status"):
            build_pain002_report(
                "x",
                "y",
                "ACCP",
                [
                    {
                        "original_payment_information_id": "p",
                        "payment_information_status": "ACCP",
                        "transaction_status": "BAD",
                    }
                ],
            )

    def test_missing_required_key_rejected(self) -> None:
        """A row missing a required key raises ValueError."""
        with pytest.raises(ValueError, match="missing key"):
            build_pain002_report(
                "x",
                "y",
                "ACCP",
                [{"payment_information_status": "ACCP"}],
            )

    def test_custom_creation_datetime_and_version(self) -> None:
        """Caller-supplied timestamp and version are honoured."""
        xml = build_pain002_report(
            "STS",
            "MSG",
            "ACCP",
            [],
            creation_datetime="2026-01-01T00:00:00+00:00",
            version="pain.002.001.10",
        )
        assert "2026-01-01T00:00:00+00:00" in xml
        assert "pain.002.001.10" in xml


class TestRoundTrip:
    """Generated reports parse back to the same data."""

    def test_group_and_payment_statuses(self, tmp_path) -> None:
        """Group + payment-info statuses survive a generate→parse round-trip."""
        xml = build_pain002_report(
            message_id="STS-1",
            original_message_id="MSG-1",
            group_status="ACCP",
            payment_statuses=[
                {
                    "original_payment_information_id": "PMT-1",
                    "payment_information_status": "ACCP",
                },
                {
                    "original_payment_information_id": "PMT-2",
                    "payment_information_status": "RJCT",
                },
            ],
        )
        parsed = parse_pain002_report(_write(tmp_path, xml))
        assert parsed["message_id"] == "STS-1"
        assert parsed["original_message_id"] == "MSG-1"
        assert parsed["group_status"] == "ACCP"
        ids = [
            (
                s["original_payment_information_id"],
                s["payment_information_status"],
            )
            for s in parsed["payment_statuses"]
        ]
        assert ids == [("PMT-1", "ACCP"), ("PMT-2", "RJCT")]

    def test_transaction_detail_round_trip(self, tmp_path) -> None:
        """Transaction status + reason survive the round-trip."""
        xml = build_pain002_report(
            "STS",
            "MSG",
            "PART",
            [
                {
                    "original_payment_information_id": "PMT-1",
                    "payment_information_status": "ACCP",
                    "original_end_to_end_id": "E2E-9",
                    "transaction_status": "RJCT",
                    "status_reason": "AC01",
                }
            ],
        )
        parsed = parse_pain002_report(_write(tmp_path, xml))
        row = parsed["payment_statuses"][0]
        assert row["original_end_to_end_id"] == "E2E-9"
        assert row["transaction_status"] == "RJCT"
        assert row["status_reason"] == "AC01"

    def test_transaction_without_reason(self, tmp_path) -> None:
        """A transaction status with no reason omits StsRsnInf and parses."""
        xml = build_pain002_report(
            "STS",
            "MSG",
            "ACCP",
            [
                {
                    "original_payment_information_id": "PMT-1",
                    "payment_information_status": "ACCP",
                    "transaction_status": "ACSC",
                }
            ],
        )
        assert "StsRsnInf" not in xml
        parsed = parse_pain002_report(_write(tmp_path, xml))
        assert parsed["payment_statuses"][0]["transaction_status"] == "ACSC"

    def test_top_level_export(self) -> None:
        """build_pain002_report is exposed at the package top level."""
        from pain001 import build_pain002_report as top

        assert top("x", "y", "ACCP", []).startswith("<?xml")


class TestSeveralTransactionsPerBlock:
    """One payment block can report several transactions (0.0.86)."""

    ROW = {
        "original_payment_information_id": "PMT-1",
        "payment_information_status": "RJCT",
        "transactions": [
            {
                "original_end_to_end_id": "E2E-1",
                "transaction_status": "RJCT",
                "status_reason": "NARR",
            },
            {"original_end_to_end_id": "E2E-2", "transaction_status": "RJCT"},
        ],
    }

    def test_one_block_holds_every_transaction(self, tmp_path) -> None:
        """Two transactions stay under one OrgnlPmtInfAndSts."""
        xml = build_pain002_report("STS", "MSG", "RJCT", [self.ROW])
        assert xml.count("<OrgnlPmtInfAndSts>") == 1
        assert xml.count("<TxInfAndSts>") == 2
        (block,) = parse_pain002_report(_write(tmp_path, xml))[
            "payment_statuses"
        ]
        assert [
            (t["original_end_to_end_id"], t["transaction_status"])
            for t in block["transactions"]
        ] == [("E2E-1", "RJCT"), ("E2E-2", "RJCT")]
        assert block["transactions"][0]["status_reason"] == "NARR"
        assert "<Cd>NARR</Cd>" in xml and xml.count("<StsRsnInf>") == 1

    def test_the_single_transaction_keys_still_work(self) -> None:
        """The flat triplet gives the same XML as a one-item list."""
        flat = {
            "original_payment_information_id": "PMT-1",
            "payment_information_status": "ACCP",
            "original_end_to_end_id": "E2E-1",
            "transaction_status": "ACCP",
        }
        listed = {
            "original_payment_information_id": "PMT-1",
            "payment_information_status": "ACCP",
            "transactions": [
                {
                    "original_end_to_end_id": "E2E-1",
                    "transaction_status": "ACCP",
                }
            ],
        }
        when = "2026-11-10T10:00:00"
        assert build_pain002_report(
            "S", "M", "ACCP", [flat], creation_datetime=when
        ) == build_pain002_report(
            "S", "M", "ACCP", [listed], creation_datetime=when
        )

    def test_both_shapes_in_one_row_are_refused(self) -> None:
        """A row with a list and the flat keys is ambiguous."""
        row = dict(self.ROW, transaction_status="RJCT")
        with pytest.raises(ValueError, match="either"):
            build_pain002_report("STS", "MSG", "RJCT", [row])

    def test_a_bad_status_in_the_list_is_refused(self) -> None:
        """Every listed transaction status is checked."""
        row = dict(
            self.ROW,
            transactions=[
                {"original_end_to_end_id": "E", "transaction_status": "NOPE"}
            ],
        )
        with pytest.raises(ValueError, match="NOPE"):
            build_pain002_report("STS", "MSG", "RJCT", [row])

    def test_a_list_entry_without_a_status_is_refused(self) -> None:
        """A listed transaction needs its status."""
        row = dict(self.ROW, transactions=[{"original_end_to_end_id": "E"}])
        with pytest.raises(ValueError, match="transaction_status"):
            build_pain002_report("STS", "MSG", "RJCT", [row])
