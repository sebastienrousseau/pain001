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

"""The shared message-type barrier both REST routers go through."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from pain001.api import app as app_module_pkg  # noqa: F401 - import side effects
from pain001.api.guards import sanitise_message_type
from pain001.constants import valid_xml_types


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_every_bundled_message_type_passes(message_type: str) -> None:
    """Allow-listed values come back unchanged."""
    assert sanitise_message_type(message_type) == message_type


@pytest.mark.parametrize(
    "bad",
    ["../../etc/passwd", "pain.001.001.99", "", "PAIN.001.001.03", "pain.001"],
)
def test_anything_else_is_a_400(bad: str) -> None:
    """A value outside the allow-list is refused before touching a path."""
    with pytest.raises(HTTPException) as excinfo:
        sanitise_message_type(bad)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid message type"


def test_app_and_dashboard_share_the_barrier() -> None:
    """The app module's private alias is the same function object."""
    import importlib

    app_module = importlib.import_module("pain001.api.app")
    ui_module = importlib.import_module("pain001.api.ui")
    assert app_module._sanitise_message_type is sanitise_message_type
    assert ui_module.sanitise_message_type is sanitise_message_type
