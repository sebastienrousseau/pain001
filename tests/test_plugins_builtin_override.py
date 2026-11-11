# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""An installed plugin cannot silently replace a built-in by name.

Plugins sit outside the trust boundary: a package that declares an
entry point named ``sepa-sct`` or ``csv`` would otherwise swap the
built-in scheme profile or loader for every run. Taking over a built-in
name needs an explicit allowance.
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest

from pain001.plugins import PAIN001_API_VERSION, PluginMeta
from pain001.plugins.registry import PluginRegistry

registry_mod = import_module("pain001.plugins.registry")


class _Entry:
    """Fake entry point for a scheme plugin; records whether it ran."""

    def __init__(self, name: str, ran: list[str], meta_name: str = "") -> None:
        self.name = name
        self.dist = None
        self._ran = ran
        self._meta_name = meta_name or name

    def load(self) -> type:
        self._ran.append(self.name)
        meta_name = self._meta_name

        class _Scheme:
            meta = PluginMeta(
                name=meta_name,
                version="1.0.0",
                description="Third-party scheme.",
                api_version=PAIN001_API_VERSION,
            )

            def validate(self, rows, *, message_type=None):  # noqa: ARG002
                return None

        return _Scheme


def _populate(reg: PluginRegistry, entries: list[_Entry]) -> None:
    """Populate ``reg`` with the real built-ins and these entry points."""
    with patch.object(
        registry_mod,
        "_iter_entry_points",
        side_effect=lambda group: (
            entries if group == "pain001.schemes" else []
        ),
    ):
        reg.list_plugins()


def test_an_entry_point_with_a_built_in_name_is_refused(monkeypatch, caplog):
    """``sepa-sct`` from a package is skipped before its code runs."""
    monkeypatch.delenv("PAIN001_ALLOW_PLUGIN_OVERRIDES", raising=False)
    caplog.set_level("WARNING", logger="pain001.plugins.registry")
    ran: list[str] = []
    reg = PluginRegistry(PAIN001_API_VERSION)
    _populate(reg, [_Entry("sepa-sct", ran), _Entry("local-scheme", ran)])
    assert ran == ["local-scheme"]
    assert reg.get_scheme("sepa-sct").meta.source == "built-in"
    assert reg.get_scheme("local-scheme").meta.description == (
        "Third-party scheme."
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "refusing scheme plugin sepa-sct" in m
        and "PAIN001_ALLOW_PLUGIN_OVERRIDES" in m
        for m in messages
    )


def test_a_built_in_meta_name_behind_another_entry_name_is_refused(
    monkeypatch,
):
    """The declared ``meta.name`` is checked as well as the entry name."""
    monkeypatch.delenv("PAIN001_ALLOW_PLUGIN_OVERRIDES", raising=False)
    ran: list[str] = []
    reg = PluginRegistry(PAIN001_API_VERSION)
    _populate(reg, [_Entry("innocent", ran, meta_name="uk-fps")])
    assert ran == ["innocent"]
    assert reg.get_scheme("uk-fps").meta.source == "built-in"


@pytest.mark.parametrize("how", ["env", "argument"])
def test_an_allowed_override_replaces_the_built_in(monkeypatch, how):
    """Naming the plugin in the allowance lets it take over."""
    monkeypatch.delenv("PAIN001_ALLOW_PLUGIN_OVERRIDES", raising=False)
    if how == "env":
        monkeypatch.setenv("PAIN001_ALLOW_PLUGIN_OVERRIDES", "other, sepa-sct")
        reg = PluginRegistry(PAIN001_API_VERSION)
    else:
        reg = PluginRegistry(PAIN001_API_VERSION, allow_overrides=["sepa-sct"])
    ran: list[str] = []
    _populate(reg, [_Entry("sepa-sct", ran)])
    assert ran == ["sepa-sct"]
    assert reg.get_scheme("sepa-sct").meta.description == (
        "Third-party scheme."
    )


def test_the_argument_survives_a_reset(monkeypatch):
    """``reset`` re-reads the environment but keeps the argument."""
    monkeypatch.delenv("PAIN001_ALLOW_PLUGIN_OVERRIDES", raising=False)
    reg = PluginRegistry(PAIN001_API_VERSION, allow_overrides=["sepa-sct"])
    reg.reset()
    ran: list[str] = []
    _populate(reg, [_Entry("sepa-sct", ran)])
    assert ran == ["sepa-sct"]
