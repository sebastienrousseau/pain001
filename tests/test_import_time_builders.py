# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Builders that run at import time, run again inside a test.

``DEFAULT_TEMPLATE_REGISTRY`` and the API's ``GENERATE_RESPONSES`` tables
are built once, when their module is imported. Tests that use them never
run the builder again, so a wrong edit to ``TemplateRegistry`` loading or
to ``generate_responses`` would only show up in what was already built.
These tests build each one afresh and compare it with the import-time
copy, then cover the inputs the bundled data does not reach.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.api.meta import (
    GENERATE_RESPONSES,
    UI_GENERATE_RESPONSES,
    generate_responses,
)
from pain001.templates.registry import (
    DEFAULT_TEMPLATE_REGISTRY,
    TemplateMetadata,
    TemplateRegistry,
)


def test_a_fresh_registry_matches_the_default_one() -> None:
    """Loading the bundled templates again gives the same records."""
    fresh = TemplateRegistry()
    assert fresh.list_supported_versions() == (
        DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
    )
    assert fresh.list_templates() == DEFAULT_TEMPLATE_REGISTRY.list_templates()


def _bundle(root: Path, name: str, metadata: str) -> Path:
    """Write ``root/name/metadata.yaml`` and return the bundle directory."""
    bundle = root / name
    bundle.mkdir()
    (bundle / "metadata.yaml").write_text(metadata, encoding="utf-8")
    return bundle


def test_metadata_with_every_field(tmp_path: Path) -> None:
    """Each metadata.yaml field lands in the record, paths resolved."""
    bundle = _bundle(
        tmp_path,
        "pain.001.001.99",
        "message_type: pain.001.001.99\n"
        "message_category: CustomerCreditTransferInitiation\n"
        "iso_version: 99\n"
        "deprecated: true\n"
        "supported_input_formats: [csv, 7]\n"
        "files:\n"
        "  template: t.xml\n"
        "  schema: s.xsd\n"
        "  example_data: d.csv\n"
        "  example_xml: x.xml\n",
    )
    registry = TemplateRegistry(tmp_path)
    assert registry.list_templates() == [
        TemplateMetadata(
            message_type="pain.001.001.99",
            message_category="CustomerCreditTransferInitiation",
            template_path=(bundle / "t.xml").resolve(),
            xsd_path=(bundle / "s.xsd").resolve(),
            example_data_path=(bundle / "d.csv").resolve(),
            example_xml_path=(bundle / "x.xml").resolve(),
            supported_input_formats=["csv", "7"],
            iso_version="99",
            deprecated=True,
        )
    ]
    assert registry.templates_dir == tmp_path.resolve()


def test_metadata_with_only_the_required_fields(tmp_path: Path) -> None:
    """Optional fields default: no examples, no formats, not deprecated."""
    bundle = _bundle(
        tmp_path,
        "pain.008.001.99",
        "message_type: pain.008.001.99\n"
        "message_category: CustomerDirectDebitInitiation\n"
        "iso_version: '99'\n"
        "files:\n"
        "  template: t.xml\n"
        "  schema: s.xsd\n",
    )
    (record,) = TemplateRegistry(tmp_path).list_templates()
    assert record == TemplateMetadata(
        message_type="pain.008.001.99",
        message_category="CustomerDirectDebitInitiation",
        template_path=(bundle / "t.xml").resolve(),
        xsd_path=(bundle / "s.xsd").resolve(),
        example_data_path=None,
        example_xml_path=None,
        supported_input_formats=[],
        iso_version="99",
        deprecated=False,
    )


def test_an_empty_metadata_file_names_the_missing_key(tmp_path: Path) -> None:
    """An empty metadata.yaml is a missing ``message_type``, not a crash."""
    _bundle(tmp_path, "empty", "")
    with pytest.raises(KeyError, match="message_type"):
        TemplateRegistry(tmp_path)


def test_bundles_are_indexed_by_message_type(tmp_path: Path) -> None:
    """The directory name does not matter; ``message_type`` keys the record."""
    for directory, message_type in (("b", "pain.001.001.98"), ("a", "x.1")):
        _bundle(
            tmp_path,
            directory,
            f"message_type: {message_type}\n"
            "message_category: C\n"
            "iso_version: 1\n"
            "files: {template: t.xml, schema: s.xsd}\n",
        )
    registry = TemplateRegistry(tmp_path)
    assert registry.list_supported_versions() == ["pain.001.001.98", "x.1"]
    assert (
        registry.get_template("x.1").template_path
        == (tmp_path / "a" / "t.xml").resolve()
    )


def test_generate_responses_documents_three_statuses() -> None:
    """400 and 500 are described; 422 carries the body or a validation error."""
    assert generate_responses("Body", "Refused") == {
        400: {"description": "Refused"},
        422: {
            "description": (
                "Rows failed validation or a scheme rule (`success: false`, "
                "with `validation_errors` or `scheme_violations`), or the "
                "request body is malformed (`detail`)"
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "anyOf": [
                            {"$ref": "#/components/schemas/Body"},
                            {
                                "$ref": "#/components/schemas/"
                                "HTTPValidationError"
                            },
                        ]
                    }
                }
            },
        },
        500: {"description": "Generation failed inside the server"},
    }


def test_the_route_tables_match_a_fresh_build() -> None:
    """The import-time tables are what the builder makes now."""
    assert GENERATE_RESPONSES == generate_responses(
        "GenerateXMLResponse", GENERATE_RESPONSES[400]["description"]
    )
    assert UI_GENERATE_RESPONSES == generate_responses(
        "UiGenerateResponse", UI_GENERATE_RESPONSES[400]["description"]
    )
