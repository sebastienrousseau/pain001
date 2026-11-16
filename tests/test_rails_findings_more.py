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

"""The rail findings in full, continued: reporting, charges, debits, references.

Regulatory reporting, charge bearer, address and UETR, direct-debit
mandates and creditor identifiers, Swiss and Swedish creditor
references, batch booking and LEIs, each pinned by rule id, column,
severity and message (see ``tests/test_rails_findings.py``).
"""

from __future__ import annotations

import pytest

from tests._rail_findings import (
    BACS_DD,
    GB,
    SWISS,
    SWISS_PLAIN_IBAN,
    Finding,
    findings,
)

AXZ = {
    "payment_currency": "USD",
    "creditor_agent_BIC": "CHASUS33",
    "charge_bearer": "SHAR",
}
UAE = {
    "payment_currency": "AED",
    "creditor_account_IBAN": "AE070331234567890123456",
}


def test_regulatory_reportingfindings() -> None:
    """Presence (code or info), and the UAE form read from the info first."""
    assert findings("de-axz", AXZ) == [
        (
            "DE-AXZ-RGLTRY",
            "regulatory_reporting_code",
            "warning",
            "Germany foreign payment (DK AXZ) expects a regulatory "
            "reporting code",
        )
    ]
    assert findings("de-axz", AXZ, regulatory_reporting_info="AWV 123") == []
    assert findings("ae-uaefts", UAE) == [
        (
            "AE-UAEFTS-RGLTRY",
            "regulatory_reporting_code",
            "error",
            "UAE UAEFTS expects a regulatory reporting code",
        )
    ]
    assert (
        findings(
            "ae-uaefts",
            UAE,
            regulatory_reporting_code="SALARY",
            regulatory_reporting_info="/BENEFRES/AE//SAL",
        )
        == []
    )
    assert findings(
        "ae-uaefts",
        UAE,
        regulatory_reporting_code="SALARY",
        regulatory_reporting_info="/OTHER/AE//SAL",
    ) == [
        (
            "AE-UAEFTS-RGLTRY",
            "regulatory_reporting_code",
            "error",
            "regulatory reporting /OTHER/AE//SAL does not follow the "
            "required form",
        )
    ]


def test_charge_bearer_address_and_uetrfindings() -> None:
    """Each names its column, its severity and what the rail expects."""
    assert findings(
        "de-axz", AXZ, charge_bearer="SLEV", regulatory_reporting_code="123"
    ) == [
        (
            "DE-AXZ-CHRGBR",
            "charge_bearer",
            "error",
            "Germany foreign payment (DK AXZ) expects charge bearer "
            "DEBT/CRED/SHAR (got SLEV)",
        )
    ]
    found = findings("cbpr-cross-border", {})
    assert [f for f in found if f[0] != "CBPR-BIC"] == [
        (
            "CBPR-CHRGBR",
            "charge_bearer",
            "error",
            "Swift CBPR+ cross-border expects charge bearer DEBT/CRED/SHAR "
            "(got None)",
        ),
        *[
            (
                "CBPR-ADDR",
                f"{party}_town",
                "error",
                f"Swift CBPR+ cross-border requires the {party} address "
                "with town and country (structured or hybrid)",
            )
            for party in ("debtor", "creditor")
        ],
        (
            "CBPR-UETR",
            "uetr",
            "warning",
            "Swift CBPR+ cross-border expects a UETR on every transaction",
        ),
    ]


def test_direct_debitfindings() -> None:
    """Sequence type, mandate presence and length, creditor identifier."""
    assert findings("uk-bacs-dd", BACS_DD) == []
    assert findings("uk-bacs-dd", BACS_DD, mandate_id="M" * 18) == []
    assert findings(
        "uk-bacs-dd", BACS_DD, sequence_type="RPRE", mandate_id="M" * 19
    ) == [
        (
            "UK-BACSDD-SEQTP",
            "sequence_type",
            "error",
            "sequence type must be one of FRST/RCUR/FNAL/OOFF (got RPRE)",
        ),
        (
            "UK-BACSDD-MNDT",
            "mandate_id",
            "error",
            "mandate id exceeds 18 characters",
        ),
    ]
    assert findings(
        "uk-bacs-dd", BACS_DD, mandate_id=None, creditor_id=None
    ) == [
        ("UK-BACSDD-MNDT", "mandate_id", "error", "mandate id is required"),
        (
            "UK-BACSDD-CDTRID",
            "creditor_id",
            "error",
            "creditor identifier (missing) does not match [0-9]{6}",
        ),
    ]
    assert findings("uk-bacs-dd", BACS_DD, creditor_id="SUN12") == [
        (
            "UK-BACSDD-CDTRID",
            "creditor_id",
            "error",
            "creditor identifier SUN12 does not match [0-9]{6}",
        )
    ]


def _cdtrref(field: str, message: str) -> Finding:
    """One Swiss creditor-reference finding."""
    return ("CH-DOM-CDTRREF", field, "error", message)


def test_swiss_qrrfindings() -> None:
    """A QRR needs 27 digits with a mod-10 check, and a QR-IBAN."""
    assert findings("ch-domestic", SWISS) == []
    assert findings(
        "ch-domestic",
        SWISS,
        creditor_reference="210000000003139471430009018",
        creditor_account_IBAN=SWISS_PLAIN_IBAN,
    ) == [
        _cdtrref(
            "creditor_reference",
            "QRR reference 210000000003139471430009018 is not 27 digits "
            "with a valid mod-10 check",
        ),
        _cdtrref(
            "creditor_account_IBAN",
            "a QRR reference requires a QR-IBAN (IID 30000-31999)",
        ),
    ]


def test_swiss_scor_and_unknown_reference_typefindings() -> None:
    """A SCOR needs a valid RF reference and a plain IBAN; else QRR or SCOR."""
    scor = {
        **SWISS,
        "creditor_reference": "RF18539007547034",
        "creditor_reference_type": "SCOR",
    }
    assert (
        findings("ch-domestic", scor, creditor_account_IBAN=SWISS_PLAIN_IBAN)
        == []
    )
    assert findings(
        "ch-domestic", scor, creditor_reference="RF00539007547034"
    ) == [
        _cdtrref(
            "creditor_reference",
            "SCOR reference RF00539007547034 is not a valid ISO 11649 RF "
            "reference",
        ),
        _cdtrref(
            "creditor_account_IBAN",
            "a QR-IBAN takes a QRR reference, not SCOR",
        ),
    ]
    assert findings("ch-domestic", scor, creditor_reference_type="OTHR") == [
        _cdtrref(
            "creditor_reference_type",
            "Swiss structured references are QRR or SCOR (got OTHR)",
        )
    ]


BANKGIRO = {
    "payment_currency": "SEK",
    "service_level_code": "NURG",
    "creditor_reference": "1234567897",
}


@pytest.mark.parametrize(
    "reference",
    ["18", "1234567890123456789012340"],
)
def test_ocr_lengths_of_two_and_twenty_five_digits_pass(
    reference: str,
) -> None:
    """The OCR length bounds are inclusive at both ends."""
    assert (
        findings("se-bankgiro", BANKGIRO, creditor_reference=reference) == []
    )


@pytest.mark.parametrize(
    "reference",
    ["12345678901234567890123459", "1234A", "1234567896"],
)
def test_ocr_references_outside_the_rules_are_flagged(reference: str) -> None:
    """Too long, not all digits, or a failed Luhn check: one finding."""
    assert findings("se-bankgiro", BANKGIRO, creditor_reference=reference) == [
        (
            "SE-BG-CDTRREF",
            "creditor_reference",
            "error",
            f"OCR reference {reference} must be 2-25 digits with a valid "
            "check digit",
        )
    ]


def test_batch_booking_and_leifindings() -> None:
    """Bankgiro's batch-booking habit, and a CHAPS LEI with bad digits."""
    assert findings("se-bankgiro", BANKGIRO, batch_booking="false") == [
        (
            "SE-BG-BATCH",
            "batch_booking",
            "warning",
            "Sweden Bankgiro is normally batch-booked true (got false)",
        )
    ]
    chaps = {
        **GB,
        "service_level_code": "SDVA",
        "purpose_code": "HLST",
        "creditor_town": "Reading",
        "creditor_country": "GB",
    }
    assert findings(
        "uk-chaps", chaps, creditor_lei="5493001KJTIIGC8Y1R13"
    ) == [
        (
            "UK-CHAPS-LEI",
            "creditor_lei",
            "error",
            "creditor_lei is not a valid LEI (check digits do not verify "
            "(ISO 17442: ISO/IEC 7064 MOD 97-10))",
        )
    ]
