# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The Bank of England's CHAPS enhanced-data rules on the ``uk-chaps`` rail.

Purpose codes become mandatory on every CHAPS payment "from November
2027" (BoE policy statement, September 2025). The rule keys on each
payment's requested execution date, never on the clock, so these tests
pin dates on both sides of the cut-over. LEIs in the tests are
synthetic (unassigned ``0000`` prefix).
"""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any

import pytest

from pain001.validation import rails
from pain001.validation.rails import RailProfile
from pain001.validation.schemes import remediation_for, validate_scheme

#: A clean CHAPS row: GBP, SDVA, domestic sort code and account, address.
ROW: dict[str, Any] = {
    "payment_currency": "GBP",
    "payment_amount": "250000.00",
    "service_level_code": "SDVA",
    "creditor_agent_clearing_system": "GBDSC",
    "creditor_agent_member_id": "309634",
    "creditor_account_id": "12345678",
    "end_to_end_id": "COMPLETION-1",
    "creditor_town": "Reading",
    "creditor_country": "GB",
    "purpose_code": "PCOM",
    "requested_execution_date": "2027-12-01",
}
GOOD_LEI = "0000006ORRMT71WEV302"
BAD_LEI = "0000006ORRMT71WEV303"


def _findings(
    rows: list[dict[str, Any]], profile: str = "uk-chaps"
) -> list[str]:
    return [
        f"{v.index}:{v.rule}:{v.severity}:{v.field}"
        for v in validate_scheme(rows, profile).violations
    ]


def _without(row: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in keys}


def test_the_cut_over_is_the_narrower_reading_of_november_2027() -> None:
    """The policy names a month, not a day: the rule starts after it."""
    assert rails.CHAPS_PURPOSE_ALL_PAYMENTS_FROM == date(2027, 12, 1)
    assert (
        rails.rail("uk-chaps").purpose_required_from
        == rails.CHAPS_PURPOSE_ALL_PAYMENTS_FROM
    )


@pytest.mark.parametrize(
    ("when", "severity"),
    [
        ({"requested_execution_date": "2026-11-11"}, "warning"),
        ({"requested_execution_date": "2027-11-30"}, "warning"),
        ({"requested_execution_date": "2027-12-01"}, "error"),
        ({"requested_execution_date": "2028-03-01"}, "error"),
        (
            {
                "requested_execution_date": None,
                "requested_execution_datetime": "2027-12-01T09:00:00",
            },
            "error",
        ),
        ({"requested_execution_date": None}, "warning"),
        ({"requested_execution_date": "1 December 2027"}, "warning"),
    ],
)
def test_a_missing_purpose_code_by_execution_date(
    when: dict[str, Any], severity: str
) -> None:
    row = {**_without(ROW, "purpose_code"), **when}
    row = {k: v for k, v in row.items() if v is not None}
    assert _findings([row]) == [f"0:UK-CHAPS-PURP:{severity}:purpose_code"]


def test_later_rows_inherit_the_batch_execution_date() -> None:
    """Row 1 carries the PmtInf header; a blank later row inherits it."""
    second = _without(ROW, "purpose_code", "requested_execution_date")
    assert _findings([ROW, second]) == ["1:UK-CHAPS-PURP:error:purpose_code"]
    early = {**ROW, "requested_execution_date": "2027-06-01"}
    assert _findings([early, second]) == [
        "1:UK-CHAPS-PURP:warning:purpose_code"
    ]


def test_the_mandate_message_names_the_date_and_source() -> None:
    (violation,) = validate_scheme(
        [_without(ROW, "purpose_code")], "uk-chaps"
    ).violations
    assert "2027-12-01" in violation.message
    assert "Bank of England" in remediation_for("UK-CHAPS-PURP")


def test_a_purpose_code_must_be_an_iso_external_code() -> None:
    assert _findings([ROW]) == []
    assert _findings([{**ROW, "purpose_code": "HLTR"}]) == [
        "0:UK-CHAPS-PURP:error:purpose_code"
    ]
    for code in ("HLRP", "HLST", "PLDS", "PDEP", "PCOM", "PLRF", "SUPP"):
        assert _findings([{**ROW, "purpose_code": code}]) == [], code


def test_a_proprietary_purpose_satisfies_presence() -> None:
    """Narrower reading: the policy does not say Prtry is refused."""
    row = {**_without(ROW, "purpose_code"), "purpose_proprietary": "HOUSE"}
    assert _findings([row]) == []


def test_the_date_can_be_moved_by_replacing_the_rail() -> None:
    """A bank that reads 'November 2027' as the 1st can say so."""
    early = dataclasses.replace(
        rails.rail("uk-chaps"), purpose_required_from=date(2027, 11, 1)
    )
    row = {
        **_without(ROW, "purpose_code"),
        "requested_execution_date": "2027-11-15",
    }
    result = RailProfile(early).validate([row])
    assert [v.severity for v in result.violations] == ["error"]
    assert _findings([row]) == ["0:UK-CHAPS-PURP:warning:purpose_code"]


@pytest.mark.parametrize(
    "column",
    ["debtor_lei", "initiator_lei", "creditor_lei", "creditor_agent_lei"],
)
def test_a_present_lei_must_verify(column: str) -> None:
    assert _findings([{**ROW, column: GOOD_LEI}]) == []
    assert _findings([{**ROW, column: BAD_LEI}]) == [
        f"0:UK-CHAPS-LEI:error:{column}"
    ]
    assert _findings([{**ROW, column: "  "}]) == []


def test_no_lei_is_required_of_a_customer_payment() -> None:
    """The BoE LEI mandate is for payments between financial institutions."""
    assert not any(key.endswith("_lei") for key in ROW)
    assert _findings([ROW]) == []
    assert "ISO 17442" in remediation_for("UK-CHAPS-LEI")


def test_other_rails_leave_lei_and_dates_alone() -> None:
    row = {
        **_without(ROW, "purpose_code"),
        "service_level_code": "URGP",
        "debtor_lei": BAD_LEI,
    }
    assert _findings([row], "uk-fps") == []


def test_the_overlay_lists_the_six_boe_property_codes() -> None:
    """BoE 2024 policy statement, section 4.1.5; each is an ISO code."""
    from pain001.corpus.rules import overlays
    from pain001.corpus.rules.external_codes import is_valid

    overlay = overlays.load_overlay(
        "scenarios/overlays/gb.boe.chaps-enhanced-data.yaml"
    )
    (rule,) = [
        r for r in overlay.rules if r.rule_id == "chaps-property-purpose"
    ]
    codes = rule.assertion.removeprefix("one_of:[").rstrip("]").split(", ")
    assert codes == ["HLRP", "HLST", "PLDS", "PDEP", "PCOM", "PLRF"]
    assert all(is_valid("ExternalPurpose1Code", code) for code in codes)
