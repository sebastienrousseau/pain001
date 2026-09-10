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

"""The synthetic identifier factories (ADR-0003, decision 5).

Published example IBANs pin every country algorithm; hypothesis then
drives seeds and countries through the factories and the project's own
validators.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pain001.corpus import identifiers as ids
from pain001.validation.bic_validator import validate_bic
from pain001.validation.iban_validator import IBAN_LENGTHS, validate_iban

BIC_PATTERN = re.compile(r"^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$")
IBAN_MARKETS = [c for c in ids.COUNTRIES if c not in ids.NON_IBAN]

# Published examples (ECBS / national registers), one per IBAN market.
PUBLISHED = {
    "GB": "GB29NWBK60161331926819",
    "FR": "FR1420041010050500013M02606",
    "NL": "NL91ABNA0417164300",
    "DE": "DE89370400440532013000",
    "IT": "IT60X0542811101000000123456",
    "BE": "BE68539007547034",
    "ES": "ES9121000418450200051332",
    "CZ": "CZ6508000000192000145399",
    "CH": "CH9300762011623852957",
    "SE": "SE4550000000058398257466",
    "LU": "LU280019400644750000",
    "QA": "QA58DOHB00001234567890ABCDEFG",
    "AE": "AE070331234567890123456",
}


@pytest.mark.parametrize(("country", "iban"), sorted(PUBLISHED.items()))
def test_published_ibans_validate_and_rebuild(country: str, iban: str) -> None:
    """mod-97 accepts them and the check digits recompute exactly."""
    assert ids.iban_is_valid(iban)
    assert ids.make_iban(country, iban[4:]) == iban
    assert ids.iban_check_digits(country, iban[4:]) == iban[2:4]


def test_iban_is_valid_rejects_bad_shapes() -> None:
    """Wrong length, wrong check digits and junk are all rejected."""
    assert not ids.iban_is_valid("DE89370400440532013001")
    assert not ids.iban_is_valid("DE8937040044053201300")
    assert not ids.iban_is_valid("12")
    assert not ids.iban_is_valid("1234567890")
    assert ids.iban_is_valid("gb29 nwbk 6016 1331 9268 19")


def test_make_iban_rejects_a_wrong_length_bban() -> None:
    """The BBAN must already have the country's length."""
    with pytest.raises(ValueError, match="must be 18 characters"):
        ids.make_iban("GB", "NWBK6016133192681")


def test_country_internal_check_digits_against_published_values() -> None:
    """Each national algorithm reproduces its published example."""
    assert ids.belgian_check("5390075470") == "34"
    assert ids.belgian_check("0000000097") == "97"  # 0 is written 97
    assert ids.french_rib_key("20041", "01005", "0500013M026") == "06"
    assert ids.italian_cin("05428", "11101", "000000123456") == "X"
    assert ids.spanish_control_digits("2100", "0418", "0200051332") == "45"
    assert ids.czech_mod11_ok("000019") and ids.czech_mod11_ok("2000145399")
    assert not ids.czech_mod11_ok("2000145398")
    assert ids.luhn_check_digit("5000000005839825746") == "6"  # SE example
    assert ids.luhn_check_digit("7992739871") == "3"
    assert ids.aba_check_digit("02100002") == "1"
    assert ids.aba_is_valid("021000021") and not ids.aba_is_valid("021000022")
    assert not ids.aba_is_valid("0210000")


def test_dutch_eleven_proof_holds() -> None:
    """The generated ten-digit number passes the weighted test."""
    number = ids.dutch_eleven_proof(ids._rng(7, "x"))
    assert len(number) == 10 and number[0] == "0"
    assert sum(int(c) * (10 - i) for i, c in enumerate(number)) % 11 == 0


def test_iban_for_rejects_non_iban_markets_and_vice_versa() -> None:
    """Each factory serves its own markets."""
    with pytest.raises(ValueError, match="no IBAN shape"):
        ids.iban_for("US", 1)
    with pytest.raises(ValueError, match="IBAN market"):
        ids.account_for("DE", 1)


@pytest.mark.parametrize("country", IBAN_MARKETS)
def test_iban_for_is_deterministic_and_country_shaped(country: str) -> None:
    """Same seed, same IBAN; different seeds differ; the length is right."""
    first, again, other = (
        ids.iban_for(country, 42),
        ids.iban_for(country, 42),
        ids.iban_for(country, 43),
    )
    assert first == again and first != other
    assert len(first) == IBAN_LENGTHS[country]
    assert first.startswith(country)


@pytest.mark.parametrize("country", sorted(ids.NON_IBAN))
def test_account_for_non_iban_markets(country: str) -> None:
    """Routing and number are digits and deterministic."""
    account = ids.account_for(country, 5)
    assert set(account) == {"routing", "number"}
    assert account["routing"].isdigit() and account["number"].isdigit()
    assert account == ids.account_for(country, 5)
    if country == "US":
        assert ids.aba_is_valid(account["routing"])


@settings(max_examples=60, deadline=None)
@given(country=st.sampled_from(IBAN_MARKETS), seed=st.integers(0, 10**9))
def test_property_generated_ibans_pass_the_project_validator(
    country: str, seed: int
) -> None:
    """Every generated IBAN is accepted by pain001's own validator."""
    iban = ids.iban_for(country, seed)
    assert ids.iban_is_valid(iban)
    assert validate_iban(iban)
    bban = iban[4:]
    if country == "BE":
        assert ids.belgian_check(bban[:10]) == bban[10:]
    if country == "FR":
        assert (
            ids.french_rib_key(bban[:5], bban[5:10], bban[10:21]) == bban[21:]
        )
    if country == "IT":
        assert ids.italian_cin(bban[1:6], bban[6:11], bban[11:]) == bban[0]
    if country == "ES":
        assert (
            ids.spanish_control_digits(bban[:4], bban[4:8], bban[10:])
            == bban[8:10]
        )
    if country == "CZ":
        assert ids.czech_mod11_ok(bban[4:10]) and ids.czech_mod11_ok(bban[10:])
    if country == "SE":
        assert ids.luhn_check_digit(bban[:19]) == bban[19]


@settings(max_examples=40, deadline=None)
@given(
    country=st.sampled_from(ids.COUNTRIES),
    seed=st.integers(0, 10**6),
    branch=st.booleans(),
)
def test_property_bics_match_the_pattern_and_are_test_bics(
    country: str, seed: int, branch: bool
) -> None:
    """Generated BICs match the ISO pattern, carry the test marker, and validate."""
    bic = ids.make_bic(country, seed, branch=branch)
    assert BIC_PATTERN.match(bic)
    assert bic[4:6] == country
    assert ids.bic_is_test(bic)
    assert len(bic) == (11 if branch else 8)
    assert validate_bic(bic)


def test_bic_is_test_marker() -> None:
    """A live BIC has no 0 in eighth place; wrong lengths are not BICs."""
    assert not ids.bic_is_test("DEUTDEFFXXX")
    assert not ids.bic_is_test("DEUTDEF0X")
    assert ids.bic_is_test("DEUTDEF0")


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10**6))
def test_property_leis_verify(seed: int) -> None:
    """Generated LEIs are 20 characters under the reserved prefix and verify."""
    lei = ids.make_lei(seed)
    assert len(lei) == 20 and lei.startswith(ids.LEI_PREFIX + "00")
    assert ids.lei_is_valid(lei)
    assert ids.lei_check_digits(lei[:18]) == lei[18:]
    assert lei == ids.make_lei(seed)


def test_lei_is_valid_on_published_and_broken_values() -> None:
    """Two registered LEIs verify; a damaged one and a short one do not."""
    assert ids.lei_is_valid("5493001KJTIIGC8Y1R12")
    assert ids.lei_is_valid("529900T8BM49AURSDO55")
    assert not ids.lei_is_valid("5493001KJTIIGC8Y1R13")
    assert not ids.lei_is_valid("5493001KJTIIGC8Y1R1")
    assert not ids.lei_is_valid("5493001KJTIIGC8Y1r12")


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10**6))
def test_property_uetrs_are_v4_uuids(seed: int) -> None:
    """UETRs are canonical v4 UUIDs and deterministic."""
    import uuid

    uetr = ids.make_uetr(seed)
    parsed = uuid.UUID(uetr)
    assert parsed.version == 4 and str(parsed) == uetr
    assert uetr == ids.make_uetr(seed)


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10**6))
def test_property_aba_numbers_verify(seed: int) -> None:
    """Routing numbers are nine digits with a valid check and a real prefix."""
    routing = ids.make_aba(seed)
    assert ids.aba_is_valid(routing)
    assert routing[0] in "0123678"


def test_mod97_helpers() -> None:
    """The ISO 7064 building blocks behave on known inputs."""
    assert ids.to_digits("AB12") == "101112"
    assert ids.mod97("DE89370400440532013000"[4:] + "DE89") == 1
    assert ids.iban_check_digits("DE", "370400440532013000") == "89"
