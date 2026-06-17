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
