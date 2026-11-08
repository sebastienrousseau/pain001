# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``PAIN001_DISABLE_PLUGINS`` stops a plugin before any of its code runs.

Skipping a disabled plugin after ``entry.load()`` is too late: loading
imports the plugin's module and instantiation runs its constructor, so
the escape hatch for a broken or hostile plugin would still execute it.
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from pain001.plugins import PAIN001_API_VERSION, PluginMeta
from pain001.plugins.registry import (
    PluginRegistry,
    _load_entry_point_plugins,
)

registry_mod = import_module("pain001.plugins.registry")


class _RecordingEntry:
    """Fake entry point whose ``load`` records that plugin code ran."""

    def __init__(self, name: str, ran: list[str]) -> None:
        self.name = name
        self.dist = None
        self._ran = ran

    def load(self) -> type:
        self._ran.append(self.name)

        class _Plugin:
            meta = PluginMeta(
                name=self.name,
                version="1.0.0",
                description="Fake entry-point plugin.",
                api_version=PAIN001_API_VERSION,
            )

        return _Plugin


def test_disabled_entry_point_is_never_loaded(monkeypatch):
    """A disabled plugin's module is not imported or instantiated."""
    monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", "evil, other")
    reg = PluginRegistry(PAIN001_API_VERSION)
    reg._populated = True
    ran: list[str] = []
    entries = [_RecordingEntry("evil", ran), _RecordingEntry("good", ran)]
    with patch.object(
        registry_mod,
        "_iter_entry_points",
        side_effect=lambda group: (
            entries if group == "pain001.writers" else []
        ),
    ):
        _load_entry_point_plugins(reg)
    assert ran == ["good"]
    assert reg.get_writer("evil") is None
    assert reg.get_writer("good") is not None
