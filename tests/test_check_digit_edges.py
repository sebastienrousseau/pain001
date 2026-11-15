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

"""Check-digit helpers, LEI reasons and purpose mandates at their edges.

The rail rules lean on these helpers; a check digit accepted or refused
wrongly is a payment accepted or refused wrongly. The values here sit
on the boundaries the algorithms define: the length limits, the digit
nine in the Luhn sum, the QR-IID range, and a carry of zero in the
Swiss recursive mod-10.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from pain001.core._support import determine_data_source_type
from pain001.validation import _check_digits as cd
from pain001.validation.lei_validator import lei_error
from pain001.validation.purpose_mandates import PurposeMandate, row_text


def test_luhn_counts_an_undoubled_nine_as_nine() -> None:
    """``59`` passes (9 + 1 = 10); ``9`` alone does not."""
    assert cd.luhn_ok("59")
    assert not cd.luhn_ok("9")


def test_aba_weights_the_fourth_digit() -> None:
    """The fourth digit carries weight 3, like the first and seventh."""
    assert cd.aba_ok("123456780")
    assert not cd.aba_ok("123356780")


def test_qrr_edges() -> None:
    """A zero carry needs check digit 0; non-digits are refused."""
    assert cd.qrr_ok("0" * 27)
    assert cd.qrr_ok("000000000000000000000000042")
    assert not cd.qrr_ok("000000000000000000000000043")
    assert not cd.qrr_ok("21000000000313947143000901A")


@pytest.mark.parametrize(
    ("reference", "valid"),
    [
        ("RF741", True),
        ("RF47" + "A" * 21, True),
        ("RF57" + "A" * 22, False),
        ("XX741", False),
    ],
)
def test_rf_reference_lengths(reference: str, valid: bool) -> None:
    """RF references are 5 to 25 characters, check digits included."""
    assert cd.rf_ok(reference) is valid


@pytest.mark.parametrize(
    ("iban", "qr"),
    [
        ("CH44 3199 9123 0008 8901 2", True),
        ("LI21 3000 0000 0000 0000 0", True),
        ("CH0030000", True),
        ("CH003000", False),
        ("CH0031999000", True),
        ("CH0032000000", False),
        ("CH0029999000", False),
    ],
)
def test_qr_iban_range_and_grouping(iban: str, qr: bool) -> None:
    """A QR-IID is 30000-31999 in a CH or LI IBAN, spaces ignored."""
    assert cd.is_qr_iban(iban) is qr


def test_lei_reasons() -> None:
    """Shape and check-digit failures each name the ISO 17442 rule."""
    assert lei_error("5493001KJTIIGC8Y1R1a") == (
        "characters 1-18 must be digits or upper-case letters and 19-20 digits"
    )
    assert lei_error("5493001KJTIIGC8Y1R13") == (
        "check digits do not verify (ISO 17442: ISO/IEC 7064 MOD 97-10)"
    )


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ([{}], "list"),
        ({"a": 1}, "dict"),
        (3, "unknown"),
        ("rows.db", "sqlite"),
        ("sqlite:///rows", "sqlite"),
        ("rows.parquet", "parquet"),
        ("rows.jsonl", "jsonl"),
        ("rows.csv", "csv"),
        ("rows.txt", "file"),
    ],
)
def test_data_source_kinds(source: object, kind: str) -> None:
    """Logs and metrics name the data source kind from its path or type."""
    assert determine_data_source_type(cast(Any, source)) == kind


def test_a_fresh_mandate_keeps_its_configuration() -> None:
    """The constructor stores what it is given and names the profile."""
    mandate = PurposeMandate(
        "HK", "HK test", "regulatory", r"[A-Z]{3}", "CNY", ("doc",)
    )
    assert (mandate.country, mandate.title, mandate.where) == (
        "HK",
        "HK test",
        "regulatory",
    )
    assert mandate.pattern is not None
    assert mandate.pattern.pattern == "[A-Z]{3}"
    assert (mandate.currency, mandate.sources) == ("CNY", ("doc",))
    assert mandate.name == "purpose-mandate-hk"
    assert PurposeMandate("QA", "QA test", "purpose").pattern is None


def _findings(
    mandate: PurposeMandate, rows: list[dict[str, str]]
) -> list[tuple[str, str, int, str | None, str]]:
    """Run a mandate and flatten its findings."""
    result = mandate.validate(rows)
    assert result.profile == mandate.name
    return [
        (v.rule, v.message, v.index, v.field, v.severity)
        for v in result.violations
    ]


def test_regulatory_mandate_findings() -> None:
    """Missing, malformed, and the legacy ``currency`` column."""
    mandate = PurposeMandate("HK", "HK test", "regulatory", r"[A-Z]{3}", "CNY")
    rows = [
        {"payment_currency": "HKD"},
        {"currency": "CNY"},
        {"payment_currency": "CNY", "regulatory_reporting_code": "cx"},
        {"payment_currency": "CNY", "regulatory_reporting_info": "CXB"},
    ]
    field = "regulatory_reporting_code"
    assert _findings(mandate, rows) == [
        ("PURP-HK", "HK test: a purpose code is mandatory", 1, field, "error"),
        (
            "PURP-HK",
            "HK test: purpose code cx does not match [A-Z]{3}",
            2,
            field,
            "error",
        ),
    ]


def test_purpose_mandate_findings() -> None:
    """A blank code falls through to the proprietary one; ISO list checked."""
    mandate = PurposeMandate("GB", "GB test", "purpose")
    rows = [
        {"purpose_code": "  ", "purpose_proprietary": "OWN1"},
        {"purpose_code": "ZZZZ"},
        {},
    ]
    assert _findings(mandate, rows) == [
        (
            "PURP-GB",
            "GB test: purpose code ZZZZ is not in the ISO external purpose "
            "list",
            1,
            "purpose_code",
            "error",
        ),
        (
            "PURP-GB",
            "GB test: a purpose code is mandatory",
            2,
            "purpose_code",
            "error",
        ),
    ]
    assert row_text({"a": " ", "b": " x "}, "a", "b") == "x"
