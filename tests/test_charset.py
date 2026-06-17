# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the ISO 20022 character-set guard."""

from pain001.validation.charset import (
    ISO20022_ALLOWED_CHARACTERS,
    find_invalid_characters,
    is_valid_charset,
    sanitize_to_charset,
)


class TestIsValidCharset:
    """Tests for is_valid_charset and find_invalid_characters."""

    def test_clean_ascii_is_valid(self) -> None:
        """Plain Latin text with permitted punctuation passes."""
        assert is_valid_charset("Invoice 12345 (ACME-Corp): ref/2026.")
        assert find_invalid_characters("Invoice 12345") == []

    def test_accented_text_is_invalid(self) -> None:
        """Accented characters are outside the permitted set."""
        assert not is_valid_charset("Café")
        assert find_invalid_characters("Café") == ["é"]

    def test_invalid_characters_are_unique_and_sorted(self) -> None:
        """Disallowed characters are returned unique and sorted."""
        assert find_invalid_characters("A&B&C@D") == ["&", "@"]

    def test_empty_string_is_valid(self) -> None:
        """An empty string trivially passes."""
        assert is_valid_charset("")
        assert find_invalid_characters("") == []

    def test_allowed_set_contents(self) -> None:
        """The permitted set includes the expected punctuation."""
        for ch in "/-?:().,'+ ":
            assert ch in ISO20022_ALLOWED_CHARACTERS
        assert "&" not in ISO20022_ALLOWED_CHARACTERS


class TestSanitizeToCharset:
    """Tests for sanitize_to_charset."""

    def test_transliterates_accents(self) -> None:
        """Accented Latin letters decompose to their base letter."""
        assert sanitize_to_charset("Café Münchën") == "Cafe Munchen"

    def test_replaces_untransliterable_with_space(self) -> None:
        """Symbols with no Latin base become the default replacement."""
        assert sanitize_to_charset("A & B") == "A   B"

    def test_custom_replacement(self) -> None:
        """A custom replacement string is honoured."""
        assert sanitize_to_charset("A & B", replacement="and") == "A and B"

    def test_output_is_always_valid(self) -> None:
        """Sanitised output always passes is_valid_charset."""
        messy = "Évä's café — 50€ #1!"
        assert is_valid_charset(sanitize_to_charset(messy))
