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

"""ISO 20022 restricted character-set validation and transliteration.

Most ISO 20022 text fields are limited to the "Latin character set"
(also called the SWIFT-x / FIN-X set). Banks routinely reject messages
that carry characters outside it — accented names, em dashes, currency
symbols pasted from spreadsheets — even when the XML is otherwise
XSD-valid. This module detects those characters and offers a best-effort
transliteration to a compliant form.

The permitted set is::

    a-z  A-Z  0-9  /  -  ?  :  (  )  .  ,  '  +  and space
"""

import unicodedata

#: The ISO 20022 "Latin character set" permitted in restricted text fields.
ISO20022_ALLOWED_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-?:().,'+ "
)


def find_invalid_characters(value: str) -> list[str]:
    """Return the characters in ``value`` outside the ISO 20022 set.

    Args:
        value: The text to inspect.

    Returns:
        A sorted list of the unique disallowed characters. Empty when the
        value is fully compliant.

    Example:
        >>> find_invalid_characters("Jose Muller & Co")
        ['&']
    """
    return sorted(
        {ch for ch in value if ch not in ISO20022_ALLOWED_CHARACTERS}
    )


def is_valid_charset(value: str) -> bool:
    """Report whether ``value`` uses only ISO 20022 permitted characters.

    Args:
        value: The text to check.

    Returns:
        ``True`` if every character is permitted, ``False`` otherwise.

    Example:
        >>> is_valid_charset("Invoice 12345")
        True
        >>> is_valid_charset("Café")
        False
    """
    return not find_invalid_characters(value)


def sanitize_to_charset(value: str, replacement: str = " ") -> str:
    """Transliterate ``value`` into the ISO 20022 character set.

    Accented Latin letters are decomposed to their base letter
    (``é`` becomes ``e``, ``ü`` becomes ``u``). Any character that still
    falls outside the permitted set is replaced with ``replacement``.

    Args:
        value: The text to transliterate.
        replacement: The string substituted for characters that cannot be
            transliterated (default: a single space).

    Returns:
        A string containing only ISO 20022 permitted characters.

    Example:
        >>> sanitize_to_charset("Café Münchën")
        'Cafe Munchen'
        >>> sanitize_to_charset("A & B", replacement="and")
        'A and B'
    """
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    )
    return "".join(
        ch if ch in ISO20022_ALLOWED_CHARACTERS else replacement
        for ch in stripped
    )
