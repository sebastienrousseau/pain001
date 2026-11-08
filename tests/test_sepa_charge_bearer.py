# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""SEPA profiles allow only the SLEV charge bearer.

Each EPC Customer-to-PSP Implementation Guideline (2025 Version 1.0)
carries the usage rule 'Only "SLEV" is allowed.' on Charge Bearer:
EPC132-08 (SCT) and EPC121-16 (SCT Inst) at pain.001 indexes 2.75 and
2.98, EPC130-08 (SDD Core) and EPC131-08 (SDD B2B) at pain.008 indexes
2.68 and 2.99. The element is optional (0..1), so an empty value passes.
"""

from __future__ import annotations

from typing import Any

import pytest

from pain001.validation import REMEDIATIONS, validate_scheme

_SEPA = ["sepa-sct", "sepa-inst", "sepa-sdd", "sepa-b2b"]


def _row(charge_bearer: Any) -> dict[str, Any]:
    return {
        "payment_currency": "EUR",
        "debtor_account_IBAN": "DE89370400440532013000",
        "creditor_account_IBAN": "FR1420041010050500013M02606",
        "service_level_code": "SEPA",
        "payment_amount": "100.00",
        "debtor_name": "John Doe",
        "creditor_name": "Acme Corp",
        "remittance_information": "Invoice 12345",
        "mandate_id": "MNDT-1",
        "sequence_type": "RCUR",
        "creditor_id": "DE98ZZZ09999999999",
        "charge_bearer": charge_bearer,
    }


def _chrgbr(profile: str, value: Any) -> list[Any]:
    result = validate_scheme([_row(value)], profile)
    return [v for v in result.violations if v.rule == "SEPA-CHRGBR"]


@pytest.mark.parametrize("profile", _SEPA)
@pytest.mark.parametrize("value", ["DEBT", "CRED", "SHAR", "OUR"])
def test_a_non_slev_charge_bearer_is_an_error(
    profile: str, value: str
) -> None:
    found = _chrgbr(profile, value)
    assert len(found) == 1
    violation = found[0]
    assert violation.severity == "error"
    assert violation.field == "charge_bearer"
    assert violation.index == 0
    assert value in violation.message
    assert violation.remediation == REMEDIATIONS["SEPA-CHRGBR"]


@pytest.mark.parametrize("profile", _SEPA)
@pytest.mark.parametrize("value", ["SLEV", " slev ", "", None])
def test_slev_or_no_charge_bearer_passes(profile: str, value: Any) -> None:
    assert _chrgbr(profile, value) == []


def test_a_row_without_the_column_passes() -> None:
    row = _row("SLEV")
    del row["charge_bearer"]
    result = validate_scheme([row], "sepa-sct")
    assert not [v for v in result.violations if v.rule == "SEPA-CHRGBR"]


def test_cross_border_keeps_accepting_other_bearers() -> None:
    assert _chrgbr("xborder-ct", "DEBT") == []
