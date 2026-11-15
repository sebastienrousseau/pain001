# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A template is checked against its schema after rendering, not before.

A raw Jinja2 template is not schema-valid XML until it is rendered, so
``validate_template_schema_compatibility`` renders it with the message
type's bundled example data and validates the result. Until 0.0.89 it
ignored the XSD verdict and reported every template valid.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.templates.registry import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation.service import ValidationService

PAIN_001 = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")


@pytest.mark.parametrize(
    "message_type", DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
)
def test_every_bundled_template_renders_valid(message_type: str) -> None:
    """Each bundled template, rendered with its example data, passes."""
    bundle = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    result = ValidationService().validate_template_schema_compatibility(
        bundle.template_path, bundle.xsd_path
    )
    assert result.is_valid, result.error


def _broken_template(tmp_path: Path) -> Path:
    """The pain.001.001.03 template with the group header renamed."""
    text = PAIN_001.template_path.read_text(encoding="utf-8")
    assert "<GrpHdr>" in text
    broken = tmp_path / "template.xml"
    broken.write_text(
        text.replace("<GrpHdr>", "<GroupHeader>").replace(
            "</GrpHdr>", "</GroupHeader>"
        ),
        encoding="utf-8",
    )
    return broken


def test_a_template_that_renders_invalid_is_reported(tmp_path: Path) -> None:
    """A template whose output breaks the schema is not compatible."""
    result = ValidationService().validate_template_schema_compatibility(
        _broken_template(tmp_path), PAIN_001.xsd_path
    )
    assert result.is_valid is False
    assert result.error is not None
    assert result.error.startswith("Schema validation failed: ")
    assert "GroupHeader" in result.error


def test_xml_that_is_not_a_template_is_checked_as_it_is(
    tmp_path: Path,
) -> None:
    """A plain document renders unchanged and is judged by the schema."""
    wrong = tmp_path / "wrong.xml"
    wrong.write_text(
        '<?xml version="1.0"?><Document xmlns="urn:iso:std:iso:20022:'
        'tech:xsd:pain.001.001.03"><Wrong/></Document>',
        encoding="utf-8",
    )
    result = ValidationService().validate_template_schema_compatibility(
        wrong, PAIN_001.xsd_path
    )
    assert result.is_valid is False
    assert result.error is not None
    assert result.error.startswith("Schema validation failed: ")


def test_the_message_type_can_be_named(tmp_path: Path) -> None:
    """A schema not named after its message type needs ``message_type``."""
    schema = tmp_path / "custom.xsd"
    schema.write_bytes(PAIN_001.xsd_path.read_bytes())
    service = ValidationService()
    unnamed = service.validate_template_schema_compatibility(
        PAIN_001.template_path, schema
    )
    assert unnamed.is_valid is False
    assert unnamed.error == (
        "Cannot tell the message type from schema 'custom.xsd'; "
        "pass message_type."
    )
    named = service.validate_template_schema_compatibility(
        PAIN_001.template_path, schema, message_type="pain.001.001.03"
    )
    assert named.is_valid, named.error


def test_a_template_outside_the_allowed_paths_is_refused(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Rendering follows generation's path rules; a refusal is invalid."""
    outside = Path("/tmp") / f"pain001-outside-{id(tmp_path_factory)}.xml"
    outside.write_text("<x/>", encoding="utf-8")
    try:
        result = ValidationService().validate_template_schema_compatibility(
            outside, PAIN_001.xsd_path
        )
    finally:
        outside.unlink()
    assert result.is_valid is False
    assert result.error is not None
    assert result.error.startswith("Template could not be rendered: ")
