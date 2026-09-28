# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Tests for pain001-fast native accelerator integration and fallbacks."""

from __future__ import annotations

import pytest

import pain001.validation.bic_validator as bic_module
import pain001.validation.charset as charset_module
import pain001.validation.iban_validator as iban_module
from pain001.validation.bic_validator import validate_bic_safe
from pain001.validation.charset import is_valid_charset
from pain001.validation.iban_validator import validate_iban_safe


class DummyFast:
    """Mock pain001_fast module for exercising fast-path delegation."""

    @staticmethod
    def validate_iban(iban: str) -> bool:
        return iban.startswith("DE89")

    @staticmethod
    def validate_bic(bic: str) -> bool:
        return bic.startswith("DEUT")

    @staticmethod
    def is_valid_charset(value: str) -> bool:
        return "Café" not in value


def test_validate_iban_safe_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test validate_iban_safe when pain001_fast is available."""
    monkeypatch.setattr(iban_module, "_FAST_AVAILABLE", True)
    monkeypatch.setattr(iban_module, "_fast", DummyFast)

    assert validate_iban_safe("DE89370400440532013000") is True
    assert validate_iban_safe("FR1420041010050500013M02606") is False


def test_validate_iban_safe_pure_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate_iban_safe fallback when pain001_fast is not available."""
    monkeypatch.setattr(iban_module, "_FAST_AVAILABLE", False)
    monkeypatch.setattr(iban_module, "_fast", None)

    assert validate_iban_safe("DE89370400440532013000") is True
    assert validate_iban_safe("INVALID_IBAN") is False


def test_validate_bic_safe_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test validate_bic_safe when pain001_fast is available."""
    monkeypatch.setattr(bic_module, "_FAST_AVAILABLE", True)
    monkeypatch.setattr(bic_module, "_fast", DummyFast)

    assert validate_bic_safe("DEUTDEFF") is True
    assert validate_bic_safe("BNPAFRPP") is False


def test_validate_bic_safe_pure_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test validate_bic_safe fallback when pain001_fast is not available."""
    monkeypatch.setattr(bic_module, "_FAST_AVAILABLE", False)
    monkeypatch.setattr(bic_module, "_fast", None)

    assert validate_bic_safe("DEUTDEFF") is True
    assert validate_bic_safe("INVALID_BIC") is False


def test_is_valid_charset_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_valid_charset when pain001_fast is available."""
    monkeypatch.setattr(charset_module, "_FAST_AVAILABLE", True)
    monkeypatch.setattr(charset_module, "_fast", DummyFast)

    assert is_valid_charset("Invoice 12345") is True
    assert is_valid_charset("Café") is False


def test_is_valid_charset_pure_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test is_valid_charset fallback when pain001_fast is not available."""
    monkeypatch.setattr(charset_module, "_FAST_AVAILABLE", False)
    monkeypatch.setattr(charset_module, "_fast", None)

    assert is_valid_charset("Invoice 12345") is True
    assert is_valid_charset("Café") is False
