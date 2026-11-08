# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

import pytest

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY


def test_registry_lists_supported_versions() -> None:
    versions = DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
    assert "pain.001.001.03" in versions
    assert "pain.001.001.12" in versions
    assert "pain.008.001.02" in versions


def test_registry_resolves_template_paths() -> None:
    template_path, schema_path = DEFAULT_TEMPLATE_REGISTRY.resolve_paths(
        "pain.001.001.12"
    )
    assert template_path.endswith("pain.001.001.12/template.xml")
    assert schema_path.endswith("pain.001.001.12/pain.001.001.12.xsd")


def test_registry_searches_by_category() -> None:
    results = DEFAULT_TEMPLATE_REGISTRY.search_by_category(
        "CustomerCreditTransferInitiation"
    )
    assert any(item.message_type == "pain.001.001.12" for item in results)


@pytest.mark.parametrize(
    ("message_type", "name"),
    [
        ("pain.001.001.03", "Customer Credit Transfer Initiation V03"),
        ("pain.001.001.13", "Customer Credit Transfer Initiation V13"),
        ("pain.008.001.08", "Customer Direct Debit Initiation V08"),
    ],
)
def test_display_name_is_the_iso_message_name(
    message_type: str, name: str
) -> None:
    """The ISO 20022 message name, as pain001-mcp shows it to a client."""
    template = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    assert template.display_name == name
