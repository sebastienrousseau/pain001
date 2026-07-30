# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

from pathlib import Path

import pytest

from pain001.templates import validate_registry
from pain001.templates.guardrails import (
    SchemaGuardrailError,
    _extract_message_type,
    validate_template_bundle,
)
from pain001.templates.registry import TemplateMetadata


def test_template_registry_guardrails_pass_for_bundled_assets() -> None:
    validated = validate_registry()
    assert "pain.001.001.12" in validated
    assert "pain.008.001.02" in validated


def _metadata(
    template: Path, xsd: Path, message_type: str
) -> TemplateMetadata:
    return TemplateMetadata(
        message_type=message_type,
        message_category="credit transfer",
        template_path=template,
        xsd_path=xsd,
        example_data_path=None,
        example_xml_path=None,
        supported_input_formats=["csv"],
        iso_version="2009",
    )


def test_extract_message_type_requires_pattern(tmp_path: Path) -> None:
    no_match = tmp_path / "plain.xml"
    no_match.write_text("<Document/>", encoding="utf-8")
    with pytest.raises(SchemaGuardrailError, match="Could not determine"):
        _extract_message_type(no_match)


def test_validate_template_bundle_missing_file(tmp_path: Path) -> None:
    metadata = _metadata(
        tmp_path / "missing.xml", tmp_path / "missing.xsd", "pain.001.001.03"
    )
    with pytest.raises(SchemaGuardrailError, match="Missing required file"):
        validate_template_bundle(metadata)


def test_validate_template_bundle_detects_drift(tmp_path: Path) -> None:
    template = tmp_path / "template.xml"
    xsd = tmp_path / "schema.xsd"
    template.write_text(
        "<Document>pain.001.001.04</Document>", encoding="utf-8"
    )
    xsd.write_text("<schema>pain.001.001.04</schema>", encoding="utf-8")
    metadata = _metadata(template, xsd, "pain.001.001.03")
    with pytest.raises(SchemaGuardrailError, match="Message type drift"):
        validate_template_bundle(metadata)
