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

"""The rail findings in full: rule id, column, severity and message.

``tests/test_rails.py`` proves each rule fires and stays quiet; this
module pins what a user reads when one fires, because the column and
the message are the contract the CLI, REST and MCP surfaces print. Each
row is validated twice so the row index is checked as well, and every
profile is built fresh so the rail's own constructor is exercised.
"""

from __future__ import annotations

import pytest

from pain001.validation import rails
from tests._rail_findings import (
    BACS_DD,
    GB,
    SWISS,
    findings,
)


def test_a_fresh_profile_takes_the_rail_name() -> None:
    """The constructor names the profile after its rail."""
    profile = rails.RailProfile(rails.rail("uk-fps"))
    assert profile.name == "uk-fps"
    assert profile.rail is rails.rail("uk-fps")


def test_an_unknown_rail_names_itself_in_the_key_error() -> None:
    """``rail`` raises KeyError carrying the name it could not find."""
    with pytest.raises(KeyError) as caught:
        rails.rail("no-such-rail")
    assert caught.value.args == ("no-such-rail",)


def test_currencyfindings() -> None:
    """A restricted rail lists its currencies; an open rail wants ISO 4217."""
    assert findings("ch-domestic", SWISS, payment_currency="USD") == [
        (
            "CH-DOM-CCY",
            "payment_currency",
            "error",
            "Switzerland domestic (SPS type D) carries CHF/EUR only (got USD)",
        )
    ]
    assert findings(
        "de-axz",
        {
            "creditor_agent_BIC": "CHASUS33",
            "charge_bearer": "SHAR",
            "regulatory_reporting_code": "123",
        },
        payment_currency="usd",
    ) == [
        (
            "DE-AXZ-CCY",
            "payment_currency",
            "error",
            "currency must be an ISO 4217 code (got usd)",
        )
    ]


def test_amount_findings_name_the_cap_and_the_currency() -> None:
    """The cap message names the currency when known and drops it when not."""
    assert findings("uk-fps", GB, payment_amount="1000000.01") == [
        (
            "UK-FPS-AMT",
            "payment_amount",
            "error",
            "UK Faster Payments items are capped at 1,000,000.00 GBP "
            "(got 1000000.01)",
        )
    ]
    assert findings("uk-fps", GB, payment_amount="1000000.00") == []
    assert findings(
        "uk-fps", GB, payment_currency=None, payment_amount="2000000"
    ) == [
        (
            "UK-FPS-CCY",
            "payment_currency",
            "error",
            "UK Faster Payments carries GBP only (got None)",
        ),
        (
            "UK-FPS-AMT",
            "payment_amount",
            "error",
            "UK Faster Payments items are capped at 1,000,000.00 (got 2000000)",
        ),
    ]


def test_service_level_and_local_instrumentfindings() -> None:
    """Service level, a rail with no instrument, and the accepted codes."""
    assert findings("uk-fps", GB, service_level_code="SDVA") == [
        (
            "UK-FPS-SVCLVL",
            "service_level_code",
            "warning",
            "UK Faster Payments expects service level URGP/URNS (got SDVA)",
        )
    ]
    bacs = {**GB, "service_level_code": "NURG"}
    assert findings("uk-bacs", bacs, local_instrument_proprietary="P1") == [
        (
            "UK-BACS-LCLINSTRM",
            "local_instrument_code",
            "warning",
            "UK Bacs Direct Credit carries no local instrument (got P1)",
        )
    ]
    assert findings("uk-bacs", bacs, local_instrument_code="C1") == [
        (
            "UK-BACS-LCLINSTRM",
            "local_instrument_code",
            "warning",
            "UK Bacs Direct Credit carries no local instrument (got C1)",
        )
    ]
    assert findings(
        "uk-bacs-dd", BACS_DD, local_instrument_proprietary="99"
    ) == [
        (
            "UK-BACSDD-LCLINSTRM",
            "local_instrument_proprietary",
            "warning",
            "local instrument 99 is not one of 01/17/18/19",
        )
    ]


def test_an_unknown_sec_code_lists_every_accepted_code() -> None:
    """US ACH names each Nacha SEC code, comma-separated and sorted."""
    sec = ", ".join(sorted(rails.SEC_CODES))
    assert sec.startswith("ACK, ADV, ARC, ATX, BOC, CCD")
    ach = {
        "payment_currency": "USD",
        "service_level_code": "NURG",
        "creditor_agent_clearing_system": "USABA",
        "creditor_agent_member_id": "021000021",
        "creditor_account_id": "123456",
    }
    assert findings("us-ach", ach, local_instrument_code="XYZ") == [
        (
            "US-ACH-LCLINSTRM",
            "local_instrument_code",
            "error",
            f"local instrument XYZ is not one of {sec}",
        )
    ]


def test_agent_bicfindings() -> None:
    """Required, both-required and malformed agent BICs."""
    sepa = {
        "payment_currency": "EUR",
        "service_level_code": "URGP",
        "creditor_account_IBAN": "DE89370400440532013000",
        "charge_bearer": "SHAR",
    }
    assert findings("de-ccu", sepa) == [
        (
            "DE-CCU-BIC",
            "creditor_agent_BIC",
            "error",
            "Germany urgent euro (DK CCU) requires the creditor agent BIC",
        )
    ]
    assert findings("de-ccu", sepa, creditor_agent_BIC="NOTABIC") == [
        (
            "DE-CCU-BIC",
            "creditor_agent_BIC",
            "error",
            "creditor agent BIC NOTABIC is not well-formed",
        )
    ]
    found = findings("cbpr-cross-border", {})
    assert [f for f in found if f[0] == "CBPR-BIC"] == [
        (
            "CBPR-BIC",
            f"{party}_agent_BIC",
            "error",
            f"Swift CBPR+ cross-border requires the {party} agent BIC",
        )
        for party in ("debtor", "creditor")
    ]


def test_a_mandate_id_alone_makes_the_debtor_the_counterparty() -> None:
    """A row with a mandate id is a direct debit even without a method."""
    row = {
        "payment_currency": "EUR",
        "service_level_code": "URGP",
        "charge_bearer": "SHAR",
        "mandate_id": "M-1",
        "debtor_account_IBAN": "DE89370400440532013000",
    }
    assert findings("de-ccu", row) == [
        (
            "DE-CCU-BIC",
            "debtor_agent_BIC",
            "error",
            "Germany urgent euro (DK CCU) requires the debtor agent BIC",
        )
    ]


def test_iban_countryfindings() -> None:
    """A missing IBAN, and a valid IBAN from outside the rail's countries."""
    assert findings("ch-domestic", SWISS, creditor_account_IBAN=None) == [
        (
            "CH-DOM-IBAN",
            "creditor_account_IBAN",
            "error",
            "Switzerland domestic (SPS type D) requires a CH/LI IBAN for "
            "the creditor",
        )
    ]
    assert findings(
        "ch-domestic",
        SWISS,
        creditor_account_IBAN="DE89370400440532013000",
        creditor_reference=None,
    ) == [
        (
            "CH-DOM-IBAN",
            "creditor_account_IBAN",
            "error",
            "creditor IBAN DE89370400440532013000 is not a valid CH/LI IBAN",
        )
    ]


def test_domestic_accountfindings() -> None:
    """An invalid IBAN, then each domestic routing-and-account finding."""
    assert findings("uk-fps", GB, creditor_account_IBAN="GB00NWBK1") == [
        (
            "UK-FPS-IBAN",
            "creditor_account_IBAN",
            "error",
            "creditor IBAN GB00NWBK1 is not valid",
        )
    ]
    assert findings(
        "uk-fps",
        GB,
        creditor_agent_clearing_system="USABA",
        creditor_agent_member_id=None,
        creditor_account_id=None,
    ) == [
        (
            "UK-FPS-MMBID",
            "creditor_agent_clearing_system",
            "error",
            "clearing system USABA is not GBDSC",
        ),
        (
            "UK-FPS-MMBID",
            "creditor_agent_member_id",
            "error",
            "UK Faster Payments needs the creditor agent's 6-digit member "
            "id or a BIC",
        ),
        (
            "UK-FPS-ACCT",
            "creditor_account_id",
            "error",
            "UK Faster Payments needs the creditor account number (8-8 "
            "digits) or an IBAN",
        ),
    ]
    assert findings(
        "uk-fps",
        GB,
        creditor_agent_member_id="12A456",
        creditor_account_id="1",
    ) == [
        (
            "UK-FPS-MMBID",
            "creditor_agent_member_id",
            "error",
            "member id 12A456 must be 6 digits",
        ),
        (
            "UK-FPS-ACCT",
            "creditor_account_id",
            "error",
            "account number 1 must be 8-8 digits",
        ),
    ]


def test_an_aba_routing_number_with_a_bad_check_digit() -> None:
    """US domestic routing numbers carry the ABA check digit."""
    ach = {
        "payment_currency": "USD",
        "service_level_code": "URNS",
        "creditor_agent_clearing_system": "USABA",
        "creditor_account_id": "123456",
    }
    assert findings("us-rtp", ach, creditor_agent_member_id="021000022") == [
        (
            "US-RTP-MMBID",
            "creditor_agent_member_id",
            "error",
            "routing number 021000022 fails the ABA check digit",
        )
    ]


def test_reference_lengthfindings() -> None:
    """End-to-end id (or payment id) and remittance ceilings are inclusive."""
    assert findings("uk-fps", GB, end_to_end_id="E" * 18) == []
    assert findings("uk-fps", GB, end_to_end_id="E" * 19) == [
        (
            "UK-FPS-REF",
            "end_to_end_id",
            "error",
            "end-to-end id exceeds 18 characters (19)",
        )
    ]
    assert findings("uk-fps", GB, end_to_end_id=None, payment_id="P" * 20) == [
        (
            "UK-FPS-REF",
            "end_to_end_id",
            "error",
            "end-to-end id exceeds 18 characters (20)",
        )
    ]
    bacs = {**GB, "service_level_code": "NURG"}
    assert findings("uk-bacs", bacs, remittance_information="R" * 18) == []
    assert findings("uk-bacs", bacs, remittance_information="R" * 19) == [
        (
            "UK-BACS-RMT",
            "remittance_information",
            "warning",
            "remittance exceeds 18 characters (19)",
        )
    ]


def test_purposefindings() -> None:
    """Expected, required, required-from-a-date, and unknown purpose codes."""
    chaps = {
        **GB,
        "service_level_code": "SDVA",
        "creditor_town": "Reading",
        "creditor_country": "GB",
    }
    expects = (
        "UK-CHAPS-PURP",
        "purpose_code",
        "warning",
        "UK CHAPS expects a purpose code",
    )
    assert findings("uk-chaps", chaps) == [expects]
    assert findings(
        "uk-chaps", chaps, requested_execution_date="2027-12-01"
    ) == [
        (
            "UK-CHAPS-PURP",
            "purpose_code",
            "error",
            "UK CHAPS requires a purpose code on payments executed from "
            "2027-12-01",
        )
    ]
    assert findings("uk-chaps", chaps, purpose_code="ZZZZ") == [
        (
            "UK-CHAPS-PURP",
            "purpose_code",
            "error",
            "purpose code ZZZZ is not in the ISO external purpose list",
        )
    ]
    qatar = {
        "payment_currency": "QAR",
        "creditor_agent_BIC": "QNBAQAQA",
        "creditor_account_IBAN": "QA58DOHB00001234567890ABCDEFG",
    }
    assert findings("qa-qatch", qatar) == [
        (
            "QA-QATCH-PURP",
            "purpose_code",
            "error",
            "Qatar QATCH credit expects a purpose code",
        )
    ]
