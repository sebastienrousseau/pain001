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

"""Small check-digit helpers the rail rules and the LEI check share.

They import nothing from the package, so any validator can use them
without an import cycle.
"""

from __future__ import annotations


def mod97_alpha(text: str) -> int:
    """MOD 97-10 over a string with letters mapped A=10 ... Z=35."""
    digits = "".join(str(int(ch, 36)) for ch in text)
    remainder = 0
    for ch in digits:
        remainder = (remainder * 10 + int(ch)) % 97
    return remainder


def luhn_ok(digits: str) -> bool:
    """True when ``digits`` pass the Luhn mod-10 check."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        value = int(ch) * (2 if i % 2 == 1 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


def aba_ok(routing: str) -> bool:
    """True when ``routing`` is nine digits with a valid ABA check digit."""
    if len(routing) != 9 or not routing.isdigit():
        return False
    d = [int(c) for c in routing]
    total = (
        3 * (d[0] + d[3] + d[6])
        + 7 * (d[1] + d[4] + d[7])
        + (d[2] + d[5] + d[8])
    )
    return total % 10 == 0


def qrr_ok(reference: str) -> bool:
    """Swiss QR reference: 27 digits, recursive mod-10 check digit."""
    if len(reference) != 27 or not reference.isdigit():
        return False
    table = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    carry = 0
    for ch in reference[:-1]:
        carry = table[(carry + int(ch)) % 10]
    return (10 - carry) % 10 == int(reference[-1])


def rf_ok(reference: str) -> bool:
    """ISO 11649 creditor reference: RF + 2 check digits + up to 21 chars."""
    compact = reference.replace(" ", "").upper()
    if not (5 <= len(compact) <= 25) or not compact.startswith("RF"):
        return False
    return mod97_alpha(compact[4:] + compact[:4]) == 1


def is_qr_iban(iban: str) -> bool:
    """A Swiss or Liechtenstein IBAN whose IID is in the QR range."""
    compact = iban.replace(" ", "")
    if compact[:2] not in ("CH", "LI") or len(compact) < 9:
        return False
    return 30000 <= int(compact[4:9]) <= 31999


__all__ = [
    "aba_ok",
    "is_qr_iban",
    "luhn_ok",
    "mod97_alpha",
    "qrr_ok",
    "rf_ok",
]
