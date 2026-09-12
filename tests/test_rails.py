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

"""The rail profiles: every configured rule fires on its own and stays quiet."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from pain001.validation import rails
from pain001.validation.schemes import (
    PROFILES,
    REMEDIATIONS,
    remediation_for,
    validate_scheme,
)

GB_ROW = {
    "payment_currency": "GBP",
    "payment_amount": "100.00",
    "service_level_code": "URGP",
    "creditor_agent_clearing_system": "GBDSC",
    "creditor_agent_member_id": "309634",
    "creditor_account_id": "12345678",
    "end_to_end_id": "REF-1",
    "remittance_information": "INV 1",
    "creditor_town": "Reading",
    "creditor_country": "GB",
    "purpose_code": "HLST",
    "charge_bearer": "SHAR",
    "debtor_agent_BIC": "BANKGB2L",
    "creditor_agent_BIC": "BANKGB2LXXX",
    "uetr": "x",
}


def _rules(profile: str, row: dict, **overrides) -> list[str]:
    merged = {**row, **overrides}
    for key, value in overrides.items():
        if value is None:
            merged.pop(key, None)
    return [
        f"{v.rule}:{v.severity}"
        for v in validate_scheme([merged], profile).violations
    ]


def test_all_rails_and_mandates_are_registered_with_hints() -> None:
    """Eighteen rails, five mandates, one remediation per rule id."""
    assert len(rails.RAILS) == 18 and len(rails.PURPOSE_MANDATES) == 5
    assert all(r.name in PROFILES for r in rails.RAILS)
    assert all(m.name in PROFILES for m in rails.PURPOSE_MANDATES)
    assert len({r.prefix for r in rails.RAILS}) == len(rails.RAILS)
    assert remediation_for("UK-FPS-AMT").startswith("Split the item")
    assert re.search(r"\bPay\.UK\b", remediation_for("UK-FPS-AMT"))
    assert remediation_for("PURP-AE")
    assert rails.rail("uk-fps").title == "UK Faster Payments"
    with pytest.raises(KeyError):
        rails.rail("nope")
    assert all(r.sources for r in rails.RAILS)
    assert rails.DESCRIPTIONS["uk-chaps"].startswith("UK CHAPS rulebook")


def test_uk_rails() -> None:
    """Bacs, FPS and CHAPS: currency, caps, service level, domestic shape, references."""
    assert _rules("uk-fps", GB_ROW) == []
    assert _rules("uk-fps", GB_ROW, payment_currency="EUR") == [
        "UK-FPS-CCY:error"
    ]
    assert _rules("uk-fps", GB_ROW, payment_amount="1000000.01") == [
        "UK-FPS-AMT:error"
    ]
    assert _rules("uk-fps", GB_ROW, payment_amount="abc") == []
    assert _rules("uk-fps", GB_ROW, service_level_code="SDVA") == [
        "UK-FPS-SVCLVL:warning"
    ]
    assert _rules("uk-fps", GB_ROW, end_to_end_id="X" * 19) == [
        "UK-FPS-REF:error"
    ]
    assert _rules("uk-fps", GB_ROW, creditor_agent_member_id="12345") == [
        "UK-FPS-MMBID:error"
    ]
    assert _rules(
        "uk-fps", GB_ROW, creditor_agent_clearing_system="USABA"
    ) == ["UK-FPS-MMBID:error"]
    assert _rules("uk-fps", GB_ROW, creditor_account_id="1234567") == [
        "UK-FPS-ACCT:error"
    ]
    assert _rules("uk-fps", GB_ROW, creditor_account_id=None) == [
        "UK-FPS-ACCT:error"
    ]
    assert _rules(
        "uk-fps",
        GB_ROW,
        creditor_agent_member_id=None,
        creditor_agent_BIC=None,
    ) == ["UK-FPS-MMBID:error"]
    assert (
        _rules(
            "uk-fps", GB_ROW, creditor_account_IBAN="GB29NWBK60161331926819"
        )
        == []
    )
    assert _rules(
        "uk-fps", GB_ROW, creditor_account_IBAN="GB29NWBK60161331926810"
    ) == ["UK-FPS-IBAN:error"]
    assert _rules("uk-fps", GB_ROW, creditor_agent_BIC="NOTABIC") == [
        "UK-FPS-BIC:error"
    ]
    assert _rules("uk-bacs", GB_ROW, service_level_code="NURG") == []
    assert _rules(
        "uk-bacs", GB_ROW, service_level_code="NURG", local_instrument_code="X"
    ) == ["UK-BACS-LCLINSTRM:warning"]
    assert _rules(
        "uk-bacs",
        GB_ROW,
        service_level_code="NURG",
        remittance_information="R" * 19,
    ) == ["UK-BACS-RMT:warning"]
    assert _rules("uk-chaps", GB_ROW, service_level_code="SDVA") == []
    assert _rules(
        "uk-chaps", GB_ROW, service_level_code="SDVA", purpose_code=None
    ) == ["UK-CHAPS-PURP:warning"]
    assert _rules(
        "uk-chaps", GB_ROW, service_level_code="SDVA", purpose_code="ZZZZ"
    ) == ["UK-CHAPS-PURP:error"]
    assert _rules(
        "uk-chaps", GB_ROW, service_level_code="SDVA", creditor_town=None
    ) == ["UK-CHAPS-ADDR:error"]


def test_uk_bacs_direct_debit() -> None:
    """SUN, mandate, sequence type, Bacs transaction codes, debtor shape."""
    row = {
        "payment_method": "DD",
        "payment_currency": "GBP",
        "payment_amount": "10.00",
        "debtor_agent_clearing_system": "GBDSC",
        "debtor_agent_member_id": "040004",
        "debtor_account_id": "12345678",
        "mandate_id": "DDI-000123",
        "sequence_type": "RCUR",
        "creditor_id": "123456",
        "local_instrument_proprietary": "17",
    }
    assert _rules("uk-bacs-dd", row) == []
    assert _rules("uk-bacs-dd", row, creditor_id="SUN12") == [
        "UK-BACSDD-CDTRID:error"
    ]
    assert _rules("uk-bacs-dd", row, creditor_id=None) == [
        "UK-BACSDD-CDTRID:error"
    ]
    assert _rules("uk-bacs-dd", row, mandate_id="M" * 19) == [
        "UK-BACSDD-MNDT:error"
    ]
    assert _rules("uk-bacs-dd", row, mandate_id=None) == [
        "UK-BACSDD-MNDT:error"
    ]
    assert _rules("uk-bacs-dd", row, sequence_type="RPRE") == [
        "UK-BACSDD-SEQTP:error"
    ]
    assert _rules("uk-bacs-dd", row, local_instrument_proprietary="99") == [
        "UK-BACSDD-LCLINSTRM:warning"
    ]
    assert _rules("uk-bacs-dd", row, debtor_account_id="ABC") == [
        "UK-BACSDD-ACCT:error"
    ]


def test_german_swiss_and_swedish_rails() -> None:
    """CCU, AXZ, Swiss QRR/SCOR pairing, Bankgiro OCR."""
    sepa = {
        "payment_currency": "EUR",
        "payment_amount": "10.00",
        "service_level_code": "URGP",
        "creditor_agent_BIC": "DEUTDEFF",
        "creditor_account_IBAN": "DE89370400440532013000",
        "charge_bearer": "SHAR",
    }
    assert _rules("de-ccu", sepa) == []
    assert _rules("de-ccu", sepa, creditor_agent_BIC=None) == [
        "DE-CCU-BIC:error"
    ]
    assert _rules("de-ccu", sepa, creditor_account_IBAN="US12") == [
        "DE-CCU-IBAN:error"
    ]
    assert _rules("de-ccu", sepa, creditor_account_IBAN=None) == [
        "DE-CCU-IBAN:error"
    ]
    assert _rules("de-ccu", sepa, charge_bearer="SLEV") == [
        "DE-CCU-CHRGBR:error"
    ]
    foreign = {
        "payment_currency": "USD",
        "payment_amount": "10.00",
        "creditor_agent_BIC": "CHASUS33",
        "charge_bearer": "SHAR",
        "regulatory_reporting_code": "123",
    }
    assert _rules("de-axz", foreign) == []
    assert _rules("de-axz", foreign, payment_currency="usd") == [
        "DE-AXZ-CCY:error"
    ]
    assert _rules("de-axz", foreign, regulatory_reporting_code=None) == [
        "DE-AXZ-RGLTRY:warning"
    ]
    swiss = {
        "payment_currency": "CHF",
        "payment_amount": "10.00",
        "creditor_account_IBAN": "CH4431999123000889012",
        "creditor_reference": "210000000003139471430009017",
        "creditor_reference_type": "QRR",
    }
    assert _rules("ch-domestic", swiss) == []
    assert _rules(
        "ch-domestic", swiss, creditor_reference="210000000003139471430009018"
    ) == ["CH-DOM-CDTRREF:error"]
    assert _rules(
        "ch-domestic", swiss, creditor_account_IBAN="CH9300762011623852957"
    ) == ["CH-DOM-CDTRREF:error"]
    scor = {
        **swiss,
        "creditor_account_IBAN": "CH9300762011623852957",
        "creditor_reference": "RF18539007547034",
        "creditor_reference_type": "SCOR",
    }
    assert _rules("ch-domestic", scor) == []
    assert _rules(
        "ch-domestic", scor, creditor_reference="RF00539007547034"
    ) == ["CH-DOM-CDTRREF:error"]
    assert _rules(
        "ch-domestic", scor, creditor_account_IBAN="CH4431999123000889012"
    ) == ["CH-DOM-CDTRREF:error"]
    assert _rules("ch-domestic", scor, creditor_reference_type="OTHR") == [
        "CH-DOM-CDTRREF:error"
    ]
    assert _rules("ch-domestic", scor, creditor_reference=None) == []
    assert _rules("ch-domestic", scor, payment_currency="USD") == [
        "CH-DOM-CCY:error"
    ]
    assert (
        _rules(
            "ch-sepa",
            {**sepa, "service_level_code": "SEPA", "charge_bearer": "SLEV"},
        )
        == []
    )
    bg = {
        "payment_currency": "SEK",
        "payment_amount": "10.00",
        "service_level_code": "NURG",
        "creditor_reference": "1234567897",
        "creditor_reference_type": "SCOR",
        "batch_booking": "true",
    }
    assert _rules("se-bankgiro", bg) == []
    assert _rules("se-bankgiro", bg, creditor_reference="1234567896") == [
        "SE-BG-CDTRREF:error"
    ]
    assert _rules("se-bankgiro", bg, creditor_reference="1") == [
        "SE-BG-CDTRREF:error"
    ]
    assert _rules("se-bankgiro", bg, batch_booking="false") == [
        "SE-BG-BATCH:warning"
    ]


def test_us_rails() -> None:
    """ACH SEC codes and ABA check digits, wire, RTP cap."""
    ach = {
        "payment_currency": "USD",
        "payment_amount": "10.00",
        "service_level_code": "NURG",
        "local_instrument_code": "CCD",
        "creditor_agent_clearing_system": "USABA",
        "creditor_agent_member_id": "021000021",
        "creditor_account_id": "123456",
        "remittance_information": "x",
    }
    assert _rules("us-ach", ach) == []
    assert _rules("us-ach", ach, local_instrument_code="XYZ") == [
        "US-ACH-LCLINSTRM:error"
    ]
    assert _rules("us-ach", ach, creditor_agent_member_id="021000022") == [
        "US-ACH-MMBID:error"
    ]
    assert _rules("us-ach", ach, remittance_information="r" * 81) == [
        "US-ACH-RMT:warning"
    ]
    wire = {
        **ach,
        "service_level_code": "URGP",
        "local_instrument_code": None,
        "charge_bearer": "DEBT",
        "creditor_town": "New York",
        "creditor_country": "US",
    }
    wire.pop("local_instrument_code")
    assert _rules("us-wire", wire) == []
    assert _rules("us-wire", wire, local_instrument_code="CCD") == [
        "US-WIRE-LCLINSTRM:warning"
    ]
    assert _rules("us-wire", wire, charge_bearer="SLEV") == [
        "US-WIRE-CHRGBR:warning"
    ]
    assert _rules("us-wire", wire, creditor_country=None) == [
        "US-WIRE-ADDR:error"
    ]
    rtp = {**wire, "service_level_code": "URNS"}
    assert _rules("us-rtp", rtp) == []
    assert _rules("us-rtp", rtp, payment_amount="10000000.01") == [
        "US-RTP-AMT:error"
    ]


def test_asian_and_gulf_rails() -> None:
    """HK FPS, SG FAST, MY DuitNow, QA QATCH, AE UAEFTS."""
    hk = {
        "payment_currency": "HKD",
        "payment_amount": "10.00",
        "service_level_code": "URGP",
        "creditor_agent_clearing_system": "HKNCC",
        "creditor_agent_member_id": "004",
        "creditor_account_id": "123456789",
    }
    assert _rules("hk-fps", hk) == []
    assert _rules("hk-fps", hk, payment_amount="1000000.01") == [
        "HK-FPS-AMT:warning"
    ]
    assert _rules("hk-fps", hk, payment_currency="USD") == ["HK-FPS-CCY:error"]
    sg = {
        "payment_currency": "SGD",
        "payment_amount": "10.00",
        "service_level_code": "URGP",
        "creditor_agent_clearing_system": "SGIBG",
        "creditor_agent_member_id": "7171001",
        "creditor_account_id": "1234567890",
        "creditor_town": "Singapore",
        "creditor_country": "SG",
    }
    assert _rules("sg-fast", sg) == []
    assert _rules("sg-fast", sg, payment_amount="200000.01") == [
        "SG-FAST-AMT:error"
    ]
    assert _rules("sg-fast", sg, creditor_town=None) == [
        "SG-FAST-ADDR:warning"
    ]
    my = {
        "payment_currency": "MYR",
        "payment_amount": "10.00",
        "creditor_agent_BIC": "MBBEMYKL",
        "purpose_code": "SALA",
    }
    assert _rules("my-duitnow", my) == []
    assert _rules("my-duitnow", my, purpose_code=None) == [
        "MY-DUITNOW-PURP:warning"
    ]
    assert _rules("my-duitnow", my, payment_amount="10000000.01") == [
        "MY-DUITNOW-AMT:warning"
    ]
    qa = {
        "payment_currency": "QAR",
        "payment_amount": "10.00",
        "creditor_agent_BIC": "QNBAQAQA",
        "creditor_account_IBAN": "QA58DOHB00001234567890ABCDEFG",
        "purpose_code": "SALA",
    }
    assert _rules("qa-qatch", qa) == []
    assert _rules("qa-qatch", qa, purpose_code=None) == ["QA-QATCH-PURP:error"]
    assert (
        _rules("qa-qatch", qa, purpose_code=None, purpose_proprietary="QCB1")
        == []
    )
    assert _rules("qa-qatch", qa, payment_amount="250000.01") == [
        "QA-QATCH-AMT:error"
    ]
    ae = {
        "payment_currency": "AED",
        "payment_amount": "10.00",
        "creditor_account_IBAN": "AE070331234567890123456",
        "regulatory_reporting_code": "SAL",
        "regulatory_reporting_info": "/BENEFRES/AE//SAL",
    }
    assert _rules("ae-uaefts", ae) == []
    assert _rules(
        "ae-uaefts",
        ae,
        regulatory_reporting_code=None,
        regulatory_reporting_info=None,
    ) == ["AE-UAEFTS-RGLTRY:error"]
    assert _rules(
        "ae-uaefts",
        ae,
        regulatory_reporting_code="SALARY",
        regulatory_reporting_info="/OTHER/AE//SAL",
    ) == ["AE-UAEFTS-RGLTRY:error"]
    assert _rules("ae-uaefts", ae, regulatory_reporting_info=None) == []


def test_cbpr_and_purpose_mandates() -> None:
    """CBPR+ agents, addresses, UETR; the five country mandates."""
    row = {
        "payment_currency": "USD",
        "payment_amount": "10.00",
        "debtor_agent_BIC": "DEUTDEFF",
        "creditor_agent_BIC": "CHASUS33",
        "debtor_town": "Berlin",
        "debtor_country": "DE",
        "creditor_town": "New York",
        "creditor_country": "US",
        "uetr": "x",
        "charge_bearer": "SHAR",
    }
    assert _rules("cbpr-cross-border", row) == []
    assert _rules("cbpr-cross-border", row, debtor_agent_BIC=None) == [
        "CBPR-BIC:error"
    ]
    assert _rules("cbpr-cross-border", row, debtor_town=None) == [
        "CBPR-ADDR:error"
    ]
    assert _rules("cbpr-cross-border", row, uetr=None) == ["CBPR-UETR:warning"]
    assert _rules("cbpr-cross-border", row, charge_bearer=None) == [
        "CBPR-CHRGBR:error"
    ]
    assert (
        _rules("purpose-mandate-ae", {"regulatory_reporting_code": "SAL"})
        == []
    )
    assert (
        _rules(
            "purpose-mandate-ae",
            {"regulatory_reporting_info": "/BENEFRES/AE//SAL"},
        )
        == []
    )
    assert _rules("purpose-mandate-ae", {}) == ["PURP-AE:error"]
    assert _rules(
        "purpose-mandate-ae", {"regulatory_reporting_code": "salary"}
    ) == ["PURP-AE:error"]
    assert _rules("purpose-mandate-qa", {"purpose_proprietary": "QCB1"}) == []
    assert _rules("purpose-mandate-my", {}) == ["PURP-MY:error"]
    assert _rules("purpose-mandate-gb", {"purpose_code": "HLST"}) == []
    assert _rules("purpose-mandate-gb", {"purpose_code": "ZZZZ"}) == [
        "PURP-GB:error"
    ]
    assert _rules("purpose-mandate-hk", {"payment_currency": "HKD"}) == []
    assert _rules("purpose-mandate-hk", {"payment_currency": "CNY"}) == [
        "PURP-HK:error"
    ]
    assert (
        _rules(
            "purpose-mandate-hk",
            {"payment_currency": "CNY", "regulatory_reporting_code": "CXBSNS"},
        )
        == []
    )


def test_composition_with_the_sepa_profiles_and_helpers() -> None:
    """Rails compose through the comma syntax; the check-digit helpers hold."""
    row = {
        **GB_ROW,
        "creditor_account_IBAN": "GB29NWBK60161331926819",
        "debtor_account_IBAN": "GB29NWBK60161331926819",
        "requested_execution_date": "2026-01-02",
    }
    combined = validate_scheme([row, row], "uk-fps,anti-duplicate")
    assert combined.profile == "uk-fps,anti-duplicate"
    assert {v.rule for v in combined.violations} == {"DUP-CREDITOR-DATE"}
    assert rails._aba_ok("021000021") and not rails._aba_ok("02100002")
    assert rails._luhn_ok("1234567897") and not rails._luhn_ok("1234567896")
    assert rails._qrr_ok("210000000003139471430009017") and not rails._qrr_ok(
        "21000000000313947143000901"
    )
    assert (
        rails._rf_ok("RF18 5390 0754 7034")
        and not rails._rf_ok("RF18")
        and not rails._rf_ok("XX18539007547034")
    )
    assert (
        rails._is_qr_iban("CH4431999123000889012")
        and not rails._is_qr_iban("DE89370400440532013000")
        and not rails._is_qr_iban("CH")
    )
    assert rails._mod97_alpha("RF18539007547034"[4:] + "RF18") == 1
    assert Decimal(rails.rail("uk-fps").max_amount or 0) == Decimal(
        "1000000.00"
    )
    assert "UK-FPS-CCY" in REMEDIATIONS


def test_rails_read_the_csv_pipeline_column_names_too() -> None:
    """The records twin writes *_account_number, *_town_name and *_country_code.

    The rails first read the short names the CLI documented before 0.0.69;
    both vocabularies must satisfy the same rule.
    """
    pipeline_row = {
        **GB_ROW,
        "creditor_account_IBAN": "",
        "creditor_account_number": "12345678",
        "creditor_agent_member_id": "040004",
        "creditor_town_name": "London",
        "creditor_country_code": "GB",
        "debtor_town_name": "Leeds",
        "debtor_country_code": "GB",
    }
    for key in ("creditor_account_id", "creditor_town", "creditor_country"):
        pipeline_row.pop(key, None)
    result = validate_scheme([pipeline_row], "uk-fps")
    assert not [v for v in result.violations if v.rule.endswith("ACCT")], (
        result.violations
    )
    chaps = validate_scheme(
        [{**pipeline_row, "payment_amount": "100.00"}], "uk-chaps"
    )
    assert not [v for v in chaps.violations if v.rule.endswith("ADDR")], (
        chaps.violations
    )
