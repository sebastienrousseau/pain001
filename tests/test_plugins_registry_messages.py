# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""What the plugin registry tells an operator, and how it discovers.

The registry's log lines and error messages are the operator's only
view of why a plugin was skipped, refused or replaced, so they are
pinned here word for word. Entry-point discovery is driven through
stand-in entry points so every branch is reached without installing a
package.
"""

from __future__ import annotations

import hashlib
import logging
import traceback
from importlib import import_module, metadata
from types import SimpleNamespace
from typing import Any

import pytest

from pain001.plugins import PAIN001_API_VERSION, PluginMeta
from pain001.plugins.registry import (
    PluginRegistry,
    PluginRegistryError,
    PluginVersionError,
)

registry_mod = import_module("pain001.plugins.registry")
LOGGER = "pain001.plugins.registry"


def _plugin(name: str, api: tuple[int, int] = PAIN001_API_VERSION) -> Any:
    """Return a bare plugin object carrying only ``meta``."""
    return SimpleNamespace(
        meta=PluginMeta(
            name=name,
            version="2.3.4",
            description="d",
            api_version=api,
            source="src-" + name,
        ),
        extensions=(".zz",),
    )


def _messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the formatted registry log messages captured so far."""
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


@pytest.mark.parametrize("kind", ["loader", "validator", "scheme", "writer"])
def test_register_without_meta_names_kind(kind: str) -> None:
    """A plugin lacking ``meta`` is refused, naming its kind."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    with pytest.raises(PluginRegistryError) as info:
        getattr(reg, f"register_{kind}")(object.__new__(object))
    message = str(info.value)
    assert message.startswith(f"{kind} plugin <object object at ")
    assert message.endswith("> missing a PluginMeta `meta` attribute")


@pytest.mark.parametrize("kind", ["loader", "validator", "scheme", "writer"])
def test_newer_major_refusal_names_kind(kind: str) -> None:
    """A plugin for a newer major API is refused with a full message."""
    reg = PluginRegistry((0, 54))
    with pytest.raises(PluginVersionError) as info:
        getattr(reg, f"register_{kind}")(_plugin("fut", (1, 2)))
    assert str(info.value) == (
        f"{kind} plugin 'fut' targets API v1.2, but this pain001 only "
        "supports up to v0.54; upgrade pain001"
    )


def test_newer_minor_warns_and_same_version_is_silent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A newer minor warns; the host's own version does not."""
    reg = PluginRegistry((0, 54))
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        reg.register_scheme(_plugin("same", (0, 54)))
        assert _messages(caplog) == []
        reg.register_scheme(_plugin("ahead", (0, 56)))
    assert _messages(caplog) == [
        "scheme plugin ahead targets API v0.56; this pain001 implements "
        "v0.54 - newer plugin methods may be ignored"
    ]
    assert reg.get_scheme("ahead") is not None


def test_disabled_plugin_is_skipped_with_info_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A plugin named in ``PAIN001_DISABLE_PLUGINS`` is logged and dropped."""
    monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", " off , other ")
    reg = PluginRegistry(PAIN001_API_VERSION)
    with caplog.at_level(logging.INFO, logger=LOGGER):
        reg.register_validator(_plugin("off"))
    assert _messages(caplog) == [
        "skipping disabled validator plugin off "
        "(set via PAIN001_DISABLE_PLUGINS)"
    ]
    assert reg._validators == {}


def test_override_warning_names_both_sources(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Replacing a plugin logs who replaced whom; the later one wins."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    first = _plugin("dup")
    second = SimpleNamespace(
        meta=PluginMeta(name="dup", version="1", description="d", source="b")
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        reg.register_writer(first)
        reg.register_writer(first)
        assert _messages(caplog) == []
        reg.register_writer(second)
    assert _messages(caplog) == [
        "writer plugin dup from b overrides existing src-dup"
    ]
    assert reg._writers["dup"] is second


def test_names_from_unset_env_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unset variable names no plugins."""
    monkeypatch.delenv("PAIN001_TEST_NAMES", raising=False)
    assert registry_mod._names_from_env("PAIN001_TEST_NAMES") == frozenset()
    monkeypatch.setenv("PAIN001_TEST_NAMES", "a,, b ,")
    assert registry_mod._names_from_env("PAIN001_TEST_NAMES") == {"a", "b"}


def test_register_by_kind_rejects_unknown_kind() -> None:
    """An unknown kind is an error that quotes the kind."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    with pytest.raises(
        PluginRegistryError, match="^unknown plugin kind: 'gadget'$"
    ):
        registry_mod._register_by_kind(reg, _plugin("x"), "gadget")


def test_stamp_source_uses_distribution_name_and_version() -> None:
    """The source becomes ``dist==version``; other meta is kept."""
    plugin = _plugin("p", (0, 1))
    entry = SimpleNamespace(
        name="ep", dist=SimpleNamespace(name="acme-pkg", version="9.1")
    )
    registry_mod._stamp_source(plugin, entry)
    assert plugin.meta == PluginMeta(
        name="p",
        version="2.3.4",
        description="d",
        api_version=(0, 1),
        source="acme-pkg==9.1",
    )


def test_stamp_source_falls_back_without_dist_details() -> None:
    """No dist uses the entry name; no version reads ``?``."""
    plugin = _plugin("p")
    registry_mod._stamp_source(plugin, SimpleNamespace(name="ep-only"))
    assert plugin.meta.source == "ep-only==?"
    entry = SimpleNamespace(name="ep", dist=SimpleNamespace(name="dist-a"))
    registry_mod._stamp_source(plugin, entry)
    assert plugin.meta.source == "dist-a==?"
    blank = SimpleNamespace(name="", version=None)
    registry_mod._stamp_source(plugin, SimpleNamespace(name="ep", dist=blank))
    assert plugin.meta.source == "ep==?"


def test_iter_entry_points_selects_only_the_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modern ``EntryPoints`` are filtered to the requested group."""
    eps = metadata.EntryPoints(
        [
            metadata.EntryPoint("a", "m:A", "pain001.loaders"),
            metadata.EntryPoint("b", "m:B", "pain001.writers"),
        ]
    )
    monkeypatch.setattr(metadata, "entry_points", lambda: eps)
    names = [
        e.name for e in registry_mod._iter_entry_points("pain001.loaders")
    ]
    assert names == ["a"]


def test_iter_entry_points_accepts_legacy_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The legacy ``dict`` shape is read by group, missing group empty."""
    legacy = {"pain001.loaders": ["entry-a"]}
    monkeypatch.setattr(metadata, "entry_points", lambda: legacy)
    assert list(registry_mod._iter_entry_points("pain001.loaders")) == [
        "entry-a"
    ]
    assert list(registry_mod._iter_entry_points("pain001.writers")) == []


builtins_mod = import_module("pain001.plugins._builtins")


def _entry(name: str, factory: Any) -> Any:
    """Return a stand-in entry point whose ``load`` yields ``factory``."""
    dist = SimpleNamespace(name="acme", version="1.0")
    return SimpleNamespace(name=name, dist=dist, load=lambda: factory)


def _populate(
    monkeypatch: pytest.MonkeyPatch, loaders: list[Any]
) -> PluginRegistry:
    """Populate a registry with one built-in ``csv`` and ``loaders`` EPs."""

    def register_all(reg: PluginRegistry) -> None:
        reg.register_loader(_plugin("csv"))

    groups = {"pain001.loaders": loaders}
    monkeypatch.setattr(builtins_mod, "register_all", register_all)
    monkeypatch.setattr(
        registry_mod, "_iter_entry_points", lambda g: groups.get(g, [])
    )
    monkeypatch.delenv("PAIN001_DISABLE_PLUGINS", raising=False)
    monkeypatch.delenv("PAIN001_ALLOW_PLUGIN_OVERRIDES", raising=False)
    return PluginRegistry(PAIN001_API_VERSION)


def _never_loaded() -> Any:
    """Fail the test if a skipped entry point is ever instantiated."""
    raise AssertionError("entry point should not have been loaded")


def test_disabled_entry_point_is_never_loaded(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A disabled entry point is logged and skipped before import."""
    reg = _populate(monkeypatch, [_entry("off", _never_loaded)])
    monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", "off")
    reg.reset()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert reg.get_loader("off") is None
    assert _messages(caplog) == [
        "skipping disabled loader plugin off before loading it "
        "(set via PAIN001_DISABLE_PLUGINS)"
    ]


def test_builtin_overrides_are_refused_and_later_entries_load(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Both refusal paths name their origin; discovery then continues."""
    reg = _populate(
        monkeypatch,
        [
            _entry("csv", _never_loaded),
            _entry("sneaky", lambda: _plugin("csv")),
            _entry("good", lambda: _plugin("good")),
        ],
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        good = reg.get_loader("good")
    tail = (
        ": it would replace the built-in of that name; "
        "set PAIN001_ALLOW_PLUGIN_OVERRIDES=csv to allow it"
    )
    assert _messages(caplog) == [
        "refusing loader plugin csv from entry point csv" + tail,
        "refusing loader plugin csv from acme==1.0" + tail,
    ]
    assert good is not None and good.meta.source == "acme==1.0"
    builtin = reg.get_loader("csv")
    assert builtin is not None and builtin.meta.source == "src-csv"


def test_failing_entry_point_logs_type_and_traceback_hash(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A crashing plugin is skipped; the log has its type and tb hash."""
    raised: list[BaseException] = []

    def broken() -> Any:
        exc = ValueError("payload that must not be logged")
        raised.append(exc)
        raise exc

    reg = _populate(monkeypatch, [_entry("bad", broken)])
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert reg.get_loader("bad") is None
    expected_hash = hashlib.sha256(
        "".join(traceback.format_tb(raised[0].__traceback__)).encode()
    ).hexdigest()
    assert expected_hash != hashlib.sha256(b"").hexdigest()
    assert _messages(caplog) == [
        "skipping loader plugin from entry-point bad: ValueError "
        f"(traceback_sha256={expected_hash})"
    ]
    record = next(r for r in caplog.records if r.name == LOGGER)
    assert record.__dict__["traceback_hash"] == expected_hash
    assert record.__dict__["exception_class"] == "ValueError"
    assert "must not be logged" not in caplog.text
