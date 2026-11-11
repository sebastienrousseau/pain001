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

"""LEI (Legal Entity Identifier) validator, ISO 17442.

ISO 17442:2012 clause 4 makes an LEI twenty characters: eighteen
alphanumeric (``18!an``) then two check digits (``2!n``). Clause 5
computes the check digits with ISO/IEC 7064 MOD 97-10 after mapping
letters to numbers (A=10 ... Z=35): append ``00`` to the eighteen
characters and take ``98 - remainder``; an LEI verifies when the whole
twenty-character string leaves remainder 1. The ISO 20022 schemas
restrict the alphanumerics to upper case (``[A-Z0-9]{18}[0-9]{2}``).

The check proves the code is well formed, not that it is registered:
only the GLEIF index says whether an LEI was issued and is current.
The LEI ROC also describes characters 5 and 6 as two reserved zeros;
that is an allocation rule for issuers, not part of the ISO check, so
it is not enforced here.

Example:
    >>> from pain001.validation.lei_validator import lei_error, validate_lei
    >>> validate_lei("0000006ORRMT71WEV302")
    True
    >>> lei_error("0000006ORRMT71WEV303")
    'check digits do not verify (ISO 17442: ISO/IEC 7064 MOD 97-10)'

Standards:
    - ISO 17442:2012, Financial services: Legal entity identifier (LEI)
    - ISO/IEC 7064:2003, check character systems (MOD 97-10)
"""

from __future__ import annotations

import re

from pain001.validation._check_digits import mod97_alpha as _mod97

#: The ISO 20022 ``LEIIdentifier`` pattern.
LEI_PATTERN = re.compile(r"[A-Z0-9]{18}[0-9]{2}")

#: An LEI's length (ISO 17442 clause 4).
LEI_LENGTH = 20


def lei_check_digits(body: str) -> str:
    """Return the two check digits for an LEI body (ISO 17442 clause 5.3).

    Args:
        body: The characters before the check digits, upper-case
            alphanumerics (eighteen for a full LEI).

    Returns:
        The check digits, zero-padded to two.
    """
    return f"{98 - _mod97(body + '00'):02d}"


def lei_error(value: str) -> str | None:
    """Return why ``value`` is not a well-formed LEI, or ``None``.

    The reason never repeats the value.

    Args:
        value: The stripped, non-empty candidate.

    Returns:
        The reason, or ``None`` when the LEI verifies.
    """
    if len(value) != LEI_LENGTH:
        return f"must be {LEI_LENGTH} characters (got {len(value)})"
    if not LEI_PATTERN.fullmatch(value):
        return (
            "characters 1-18 must be digits or upper-case letters and "
            "19-20 digits"
        )
    if _mod97(value) != 1:
        return "check digits do not verify (ISO 17442: ISO/IEC 7064 MOD 97-10)"
    return None


def validate_lei(value: str) -> bool:
    """Return True when ``value`` is a well-formed ISO 17442 LEI.

    Args:
        value: The candidate LEI.

    Returns:
        Whether its length, characters and check digits are all valid.
    """
    return lei_error(value) is None


__all__ = [
    "LEI_LENGTH",
    "LEI_PATTERN",
    "lei_check_digits",
    "lei_error",
    "validate_lei",
]
