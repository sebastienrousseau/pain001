# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Pin the exact errors raised for an unknown message type.

``required_columns`` and ``TemplateRegistry.get_template`` both name
the message types they know when given one they do not. Earlier tests
matched that text with a regex search, so the mutation ratchet found
mutants that changed it and survived. These tests compare it whole.
"""

from __future__ import annotations

import pytest

from pain001.constants import valid_xml_types
from pain001.schemas.required_columns import required_columns
from pain001.templates.registry import DEFAULT_TEMPLATE_REGISTRY


def test_required_columns_names_the_known_types() -> None:
    with pytest.raises(ValueError) as caught:
        required_columns("pain.999")
    known = ", ".join(valid_xml_types)
    assert (
        str(caught.value) == f"Unknown message type 'pain.999'. Known: {known}"
    )


def test_required_columns_for_a_type_is_a_fresh_dict() -> None:
    first = required_columns("pain.001.001.09")
    first.clear()
    assert required_columns("pain.001.001.09") != {}


def test_get_template_names_the_known_types() -> None:
    with pytest.raises(KeyError) as caught:
        DEFAULT_TEMPLATE_REGISTRY.get_template("pain.999")
    known = ", ".join(DEFAULT_TEMPLATE_REGISTRY.list_supported_versions())
    assert caught.value.args == (
        f"Unsupported template 'pain.999'. Known values: {known}",
    )
    assert isinstance(caught.value.__cause__, KeyError)
    assert caught.value.__cause__.args == ("pain.999",)
