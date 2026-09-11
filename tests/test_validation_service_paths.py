# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Failure paths of the validation service that need unusual inputs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import pain001.validation.service as service_module
from pain001.exceptions import SchemaValidationError
from pain001.validation.service import ValidationService

TEMPLATE = Path("pain001/templates/pain.001.001.03/template.xml")
SCHEMA = Path("pain001/templates/pain.001.001.03/pain.001.001.03.xsd")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_data_source_must_be_a_regular_file(tmp_path: Path) -> None:
    """A named pipe exists and is not a directory, yet is not a data file."""
    pipe = tmp_path / "rows.csv"
    os.mkfifo(pipe)
    result = ValidationService().validate_data_source(pipe)
    assert result.is_valid is False
    assert "does not exist" in (result.error or "")


def test_template_schema_mismatch_is_reported(monkeypatch) -> None:
    def fail(*_args: object) -> None:
        raise SchemaValidationError("element out of order")

    monkeypatch.setattr(service_module, "validate_via_xsd", fail)
    result = ValidationService().validate_template_schema_compatibility(
        TEMPLATE, SCHEMA
    )
    assert result.is_valid is False
    assert "Schema validation failed" in (result.error or "")


def test_template_schema_unexpected_error_is_reported(monkeypatch) -> None:
    def crash(*_args: object) -> None:
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(service_module, "validate_via_xsd", crash)
    result = ValidationService().validate_template_schema_compatibility(
        TEMPLATE, SCHEMA
    )
    assert result.is_valid is False
    assert "Unexpected schema validation error" in (result.error or "")


def test_data_content_reports_data_source_errors(tmp_path: Path) -> None:
    """An empty JSONL file is a data source error, not a value error."""
    empty = tmp_path / "rows.jsonl"
    empty.write_text("\n", encoding="utf-8")
    result = ValidationService().validate_data_content(empty)
    assert result.is_valid is False
    assert "Data source error" in (result.error or "")
