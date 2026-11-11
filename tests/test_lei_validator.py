# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""ISO 17442 LEIs: twenty characters, MOD 97-10 check digits.

Every full LEI here is synthetic: it carries the ``0000`` prefix no
Local Operating Unit has been assigned (``pain001.corpus.identifiers``),
so it can never be a registered entity's code.
"""

from __future__ import annotations

import pytest

from pain001.corpus import identifiers
from pain001.validation.lei_validator import (
    lei_check_digits,
    lei_error,
    validate_lei,
)

#: Synthetic LEIs whose check digits verify.
GOOD = ("0000006ORRMT71WEV302", "000000MKEGLALP57A130", "0000001H3HPJKC5XII40")


@pytest.mark.parametrize("lei", GOOD)
def test_a_synthetic_lei_verifies(lei: str) -> None:
    assert lei_error(lei) is None
    assert validate_lei(lei)


def test_the_iso_17442_annex_a_check_digit_example() -> None:
    """ISO 17442:2012 Annex A.1: ``A1234567`` takes check digits 02."""
    assert lei_check_digits("A1234567") == "02"


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("0000006ORRMT71WEV30", "20 characters"),
        ("0000006ORRMT71WEV3021", "20 characters"),
        ("0000006orrmt71wev302", "upper-case letters"),
        ("0000006ORRMT71WEV3A2", "upper-case letters"),
        ("0000006ORRMT71-EV302", "upper-case letters"),
        ("0000006ORRMT71WEV303", "check digits"),
        ("0000006ORRMT71WEV203", "check digits"),
    ],
)
def test_a_broken_lei_says_why(value: str, reason: str) -> None:
    error = lei_error(value)
    assert error is not None and reason in error
    assert value not in error
    assert not validate_lei(value)


def test_the_corpus_generator_uses_the_same_rule() -> None:
    """One implementation: the corpus helpers delegate to the validator."""
    for seed in range(50):
        lei = identifiers.make_lei(seed)
        assert validate_lei(lei) and identifiers.lei_is_valid(lei)
    assert identifiers.lei_check_digits("A1234567") == "02"
    assert not identifiers.lei_is_valid("0000006ORRMT71WEV303")
