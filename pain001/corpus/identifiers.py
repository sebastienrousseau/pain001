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

"""Synthetic identifiers that pass every structural check (ADR-0003, 5).

Corpus files need account numbers, BICs and LEIs that validators
accept without pointing at anyone's real account. Every factory here
is deterministic in its ``seed``, so a scenario renders the same bytes
on every build, and produces values that satisfy the published
structure: IBAN mod-97 with the country's BBAN shape and its internal
check digits (Belgian mod 97, French RIB key, Italian CIN, Spanish
control digits, Czech mod 11, Swedish Luhn over clearing and account, Dutch
eleven-proof), the
SWIFT BIC pattern in its test-and-training form (``0`` as the eighth
character), ISO 17442 LEIs under an unassigned LOU prefix, ABA routing
numbers with their check digit, and RFC 4122 v4-shaped UETRs.

Real public routing codes (sort codes, BLZ, ABI/CAB, bank codes) are
fine to use and the scenarios do; the account parts are synthetic.
"""

from __future__ import annotations

import random
import string
import uuid
from collections.abc import Callable

from pain001.validation.iban_validator import IBAN_LENGTHS

#: The sixteen markets of the plan; "SW" covers Switzerland and Sweden.
COUNTRIES: tuple[str, ...] = (
    "GB", "FR", "NL", "DE", "IT", "BE", "ES", "US", "CZ",
    "CH", "SE", "LU", "HK", "SG", "MY", "QA", "AE",
)  # fmt: skip

#: Markets whose accounts are not expressed as IBANs.
NON_IBAN: frozenset[str] = frozenset({"US", "HK", "SG", "MY"})

#: An LOU prefix no operator has been assigned, so a corpus LEI can
#: never collide with a registered one.
LEI_PREFIX = "0000"

_ALNUM = string.digits + string.ascii_uppercase


def _rng(seed: int, salt: str) -> random.Random:
    """A generator that depends on the seed and the factory using it."""
    return random.Random(f"{salt}:{seed}")


def _digits(rng: random.Random, n: int) -> str:
    """``n`` random decimal digits."""
    return "".join(rng.choice(string.digits) for _ in range(n))


def _letters(rng: random.Random, n: int) -> str:
    """``n`` random upper-case letters."""
    return "".join(rng.choice(string.ascii_uppercase) for _ in range(n))


def _alnum(rng: random.Random, n: int) -> str:
    """``n`` random digits or upper-case letters."""
    return "".join(rng.choice(_ALNUM) for _ in range(n))


def to_digits(text: str) -> str:
    """Map letters to two-digit values (A=10 ... Z=35), as ISO 7064 does.

    Args:
        text: Digits and upper-case letters.

    Returns:
        The digit string.
    """
    return "".join(str(int(ch, 36)) for ch in text)


def mod97(text: str) -> int:
    """ISO 7064 MOD 97-10 remainder of a digit-and-letter string."""
    remainder = 0
    for chunk in to_digits(text):
        remainder = (remainder * 10 + int(chunk)) % 97
    return remainder


def iban_check_digits(country: str, bban: str) -> str:
    """The two check digits that make ``country + ?? + bban`` valid."""
    return f"{98 - mod97(bban + country + '00'):02d}"


def iban_is_valid(iban: str) -> bool:
    """True when the IBAN has its country's length and mod-97 remainder 1."""
    compact = iban.replace(" ", "").upper()
    if len(compact) < 5 or not compact[:2].isalpha():
        return False
    expected = IBAN_LENGTHS.get(compact[:2])
    if expected is not None and len(compact) != expected:
        return False
    return mod97(compact[4:] + compact[:4]) == 1


def make_iban(country: str, bban: str) -> str:
    """Assemble a valid IBAN from a country and its BBAN.

    Args:
        country: ISO 3166 alpha-2 code.
        bban: The basic bank account number, already shaped.

    Returns:
        The IBAN.

    Raises:
        ValueError: If the BBAN length does not match the country.
    """
    expected = IBAN_LENGTHS.get(country)
    if expected is not None and len(bban) != expected - 4:
        raise ValueError(
            f"{country} BBAN must be {expected - 4} characters, got {len(bban)}"
        )
    return f"{country}{iban_check_digits(country, bban)}{bban}"


# --- Per-country BBAN shapes and their internal check digits ---------------


def belgian_check(body: str) -> str:
    """Belgian account check: body mod 97, with 0 written as 97."""
    remainder = int(body) % 97
    return f"{remainder or 97:02d}"


def french_rib_key(bank: str, branch: str, account: str) -> str:
    """The RIB key: 97 minus (89·bank + 15·branch + 3·account) mod 97."""
    table = {
        ch: str((i % 9) + 1) for i, ch in enumerate(string.ascii_uppercase)
    }
    digits = "".join(table.get(ch, ch) for ch in account)
    key = 97 - ((89 * int(bank) + 15 * int(branch) + 3 * int(digits)) % 97)
    return f"{key:02d}"


_CIN_ODD = {
    **{str(d): v for d, v in enumerate([1, 0, 5, 7, 9, 13, 15, 17, 19, 21])},
    **dict(
        zip(
            string.ascii_uppercase,
            [
                1,
                0,
                5,
                7,
                9,
                13,
                15,
                17,
                19,
                21,
                2,
                4,
                18,
                20,
                11,
                3,
                6,
                8,
                12,
                14,
                16,
                10,
                22,
                25,
                24,
                23,
            ],
            strict=True,
        )
    ),
}
_CIN_EVEN = {
    **{str(d): d for d in range(10)},
    **{ch: i for i, ch in enumerate(string.ascii_uppercase)},
}


def italian_cin(abi: str, cab: str, account: str) -> str:
    """The CIN control letter over ABI + CAB + account."""
    total = 0
    for i, ch in enumerate(abi + cab + account):
        total += _CIN_ODD[ch] if i % 2 == 0 else _CIN_EVEN[ch]
    return string.ascii_uppercase[total % 26]


def spanish_control_digits(bank: str, branch: str, account: str) -> str:
    """The two Spanish DC digits over bank+branch and account."""
    weights = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]

    def digit(text: str) -> str:
        """One control digit over ``text`` with the Spanish weights."""
        total = sum(int(ch) * w for ch, w in zip(text, weights, strict=True))
        value = 11 - (total % 11)
        return str({10: 1, 11: 0}.get(value, value))

    return digit("00" + bank + branch) + digit(account)


def czech_mod11_ok(number: str) -> bool:
    """Czech prefix/account numbers weight 6,3,7,9,10,5,8,4,2,1 mod 11."""
    weights = [6, 3, 7, 9, 10, 5, 8, 4, 2, 1]
    padded = number.rjust(10, "0")
    return (
        sum(int(ch) * w for ch, w in zip(padded, weights, strict=True)) % 11
        == 0
    )


def czech_number(rng: random.Random, length: int) -> str:
    """A number of ``length`` digits that passes the Czech mod-11 check."""
    while True:
        candidate = _digits(rng, length)
        if czech_mod11_ok(candidate):
            return candidate


def luhn_check_digit(body: str) -> str:
    """The Luhn (mod 10) check digit that completes ``body``."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        value = int(ch) * (2 if i % 2 == 0 else 1)
        total += value - 9 if value > 9 else value
    return str((10 - total % 10) % 10)


def dutch_eleven_proof(rng: random.Random) -> str:
    """A ten-digit Dutch account number that passes the eleven-proof."""
    while True:
        candidate = "0" + _digits(rng, 9)
        weighted = sum(int(ch) * (10 - i) for i, ch in enumerate(candidate))
        if weighted % 11 == 0:
            return candidate


def aba_check_digit(first_eight: str) -> str:
    """The ninth digit of an ABA routing number."""
    d = [int(ch) for ch in first_eight]
    total = 3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5])
    return str((10 - total % 10) % 10)


def make_aba(seed: int) -> str:
    """A nine-digit ABA routing number with a valid check digit."""
    rng = _rng(seed, "aba")
    first = str(rng.choice([0, 1, 2, 3, 6, 7, 8])) + _digits(rng, 7)
    return first + aba_check_digit(first)


def aba_is_valid(routing: str) -> bool:
    """True when ``routing`` is nine digits with the right check digit."""
    return (
        len(routing) == 9
        and routing.isdigit()
        and aba_check_digit(routing[:8]) == routing[8]
    )


def _bban_gb(rng: random.Random) -> str:
    """Bank code (4 letters), sort code (6) and account (8)."""
    return _letters(rng, 4) + _digits(rng, 6) + _digits(rng, 8)


def _bban_fr(rng: random.Random) -> str:
    """Bank (5), branch (5), account (11 alphanumeric) and RIB key (2)."""
    bank, branch, account = _digits(rng, 5), _digits(rng, 5), _alnum(rng, 11)
    return bank + branch + account + french_rib_key(bank, branch, account)


def _bban_nl(rng: random.Random) -> str:
    """Bank code (4 letters) and a ten-digit eleven-proof account."""
    return _letters(rng, 4) + dutch_eleven_proof(rng)


def _bban_de(rng: random.Random) -> str:
    """Bankleitzahl (8) and account (10)."""
    return _digits(rng, 8) + _digits(rng, 10)


def _bban_it(rng: random.Random) -> str:
    """CIN letter, ABI (5), CAB (5) and account (12 alphanumeric)."""
    abi, cab, account = _digits(rng, 5), _digits(rng, 5), _alnum(rng, 12)
    return italian_cin(abi, cab, account) + abi + cab + account


def _bban_be(rng: random.Random) -> str:
    """Bank (3), account (7) and the mod-97 check (2)."""
    body = _digits(rng, 3) + _digits(rng, 7)
    return body + belgian_check(body)


def _bban_es(rng: random.Random) -> str:
    """Bank (4), branch (4), control digits (2) and account (10)."""
    bank, branch, account = _digits(rng, 4), _digits(rng, 4), _digits(rng, 10)
    return (
        bank + branch + spanish_control_digits(bank, branch, account) + account
    )


def _bban_cz(rng: random.Random) -> str:
    """Bank (4), prefix (6) and account (10), both mod-11 checked."""
    return _digits(rng, 4) + czech_number(rng, 6) + czech_number(rng, 10)


def _bban_ch(rng: random.Random) -> str:
    """Clearing number (5) and account (12)."""
    return _digits(rng, 5) + _digits(rng, 12)


def _bban_se(rng: random.Random) -> str:
    """Clearing (3), account (16) and a Luhn digit over both."""
    body = _digits(rng, 3) + _digits(rng, 16)  # clearing + account
    return body + luhn_check_digit(body)


def _bban_lu(rng: random.Random) -> str:
    """Bank (3) and account (13 alphanumeric)."""
    return _digits(rng, 3) + _alnum(rng, 13)


def _bban_qa(rng: random.Random) -> str:
    """Bank code (4 letters) and account (21 alphanumeric)."""
    return _letters(rng, 4) + _alnum(rng, 21)


def _bban_ae(rng: random.Random) -> str:
    """Bank (3) and account (16)."""
    return _digits(rng, 3) + _digits(rng, 16)


_BBAN: dict[str, Callable[[random.Random], str]] = {
    "GB": _bban_gb,
    "FR": _bban_fr,
    "NL": _bban_nl,
    "DE": _bban_de,
    "IT": _bban_it,
    "BE": _bban_be,
    "ES": _bban_es,
    "CZ": _bban_cz,
    "CH": _bban_ch,
    "SE": _bban_se,
    "LU": _bban_lu,
    "QA": _bban_qa,
    "AE": _bban_ae,
}


def iban_for(country: str, seed: int) -> str:
    """A valid, synthetic IBAN in the country's BBAN shape.

    Args:
        country: One of the IBAN markets in :data:`COUNTRIES`.
        seed: Any integer; the same seed gives the same IBAN.

    Returns:
        The IBAN.

    Raises:
        ValueError: If the country has no IBAN shape here.
    """
    shape = _BBAN.get(country)
    if shape is None:
        raise ValueError(
            f"no IBAN shape for {country!r}; IBAN markets: "
            f"{', '.join(sorted(_BBAN))}"
        )
    return make_iban(country, shape(_rng(seed, f"iban:{country}")))


def account_for(country: str, seed: int) -> dict[str, str]:
    """A domestic account identification for a non-IBAN market.

    Args:
        country: ``US``, ``HK``, ``SG`` or ``MY``.
        seed: Any integer.

    Returns:
        ``{"routing": ..., "number": ...}`` with the market's routing
        identifier (ABA number, HK bank+branch, SG bank+branch, MY bank
        code) and a synthetic account number.

    Raises:
        ValueError: If the country is an IBAN market.
    """
    rng = _rng(seed, f"account:{country}")
    if country == "US":
        return {"routing": make_aba(seed), "number": _digits(rng, 10)}
    if country == "HK":
        return {
            "routing": _digits(rng, 3) + _digits(rng, 3),
            "number": _digits(rng, 9),
        }
    if country == "SG":
        return {
            "routing": _digits(rng, 4) + _digits(rng, 3),
            "number": _digits(rng, 10),
        }
    if country == "MY":
        return {"routing": _digits(rng, 4), "number": _digits(rng, 14)}
    raise ValueError(f"{country!r} is an IBAN market; use iban_for")


# --- BIC, LEI, UETR ----------------------------------------------------------


def make_bic(country: str, seed: int, branch: bool = False) -> str:
    """A BIC in the SWIFT test-and-training form.

    The eighth character is ``0``, which SWIFT reserves for test BICs,
    so the value matches the ISO pattern and can never be a live
    institution's code.

    Args:
        country: ISO 3166 alpha-2 code for characters five and six.
        seed: Any integer.
        branch: Append a three-character branch code.

    Returns:
        An eight- or eleven-character BIC.
    """
    rng = _rng(seed, f"bic:{country}")
    location = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ23456789")
    bic = _letters(rng, 4) + country.upper() + location + "0"
    return bic + (_alnum(rng, 3) if branch else "")


def bic_is_test(bic: str) -> bool:
    """True when the BIC carries the test-and-training marker."""
    return len(bic) in (8, 11) and bic[7] == "0"


def lei_check_digits(body: str) -> str:
    """ISO 17442 check digits (MOD 97-10 over the 18-character body)."""
    return f"{98 - mod97(body + '00'):02d}"


def make_lei(seed: int) -> str:
    """A structurally valid LEI under :data:`LEI_PREFIX`.

    Args:
        seed: Any integer.

    Returns:
        A twenty-character LEI whose check digits verify.
    """
    body = LEI_PREFIX + "00" + _alnum(_rng(seed, "lei"), 12)
    return body + lei_check_digits(body)


def lei_is_valid(lei: str) -> bool:
    """True when ``lei`` is twenty characters and passes MOD 97-10."""
    return (
        len(lei) == 20 and all(ch in _ALNUM for ch in lei) and mod97(lei) == 1
    )


def make_uetr(seed: int) -> str:
    """A deterministic RFC 4122 version-4-shaped UUID for ``PmtId/UETR``.

    Args:
        seed: Any integer.

    Returns:
        The canonical lower-case hyphenated form.
    """
    rng = _rng(seed, "uetr")
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


__all__ = [
    "COUNTRIES",
    "LEI_PREFIX",
    "NON_IBAN",
    "aba_check_digit",
    "aba_is_valid",
    "account_for",
    "belgian_check",
    "bic_is_test",
    "czech_mod11_ok",
    "dutch_eleven_proof",
    "french_rib_key",
    "iban_check_digits",
    "iban_for",
    "iban_is_valid",
    "italian_cin",
    "lei_check_digits",
    "lei_is_valid",
    "luhn_check_digit",
    "make_aba",
    "make_bic",
    "make_iban",
    "make_lei",
    "make_uetr",
    "mod97",
    "spanish_control_digits",
    "to_digits",
]
