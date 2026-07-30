# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Regression tests for the pain001 plugin contract (issue v0.0.54 #1).

The plugin substrate is a one-way-door API: once external packages
ship against ``pain001.plugins``, every Protocol shape and registry
behaviour is locked in for the major. These tests pin the surface so
accidental drift can't sneak through.
"""

from __future__ import annotations

import pytest

from pain001.plugins import (
    PAIN001_API_VERSION,
    AbstractLoader,
    AbstractScheme,
    AbstractValidator,
    AbstractWriter,
    LoaderResult,
    PluginInfo,
    PluginMeta,
    PluginRegistry,
    PluginRegistryError,
    PluginVersionError,
    SchemeFinding,
    SchemeResult,
    ValidatorFinding,
    ValidatorResult,
)
from pain001.plugins.registry import registry as global_registry


# ---------------------------------------------------------------------------
# Protocol shape: every contract is runtime-checkable
# ---------------------------------------------------------------------------
class _OkLoader:
    meta = PluginMeta(
        name="ok", version="0.0.0", description="test", source="built-in"
    )
    extensions = (".ok",)

    def load(self, path: str) -> LoaderResult:
        return LoaderResult(rows=[{"path": path}], source_hint=path)

    def load_streaming(self, path: str, chunk_size: int):
        yield self.load(path)


class _OkValidator:
    meta = PluginMeta(
        name="ok-v", version="0.0.0", description="test", source="built-in"
    )

    def validate(self, rows, *, message_type):
        return ValidatorResult(is_valid=True, findings=[])


class _OkScheme:
    meta = PluginMeta(
        name="ok-s", version="0.0.0", description="test", source="built-in"
    )

    def validate(self, rows, *, message_type):
        return SchemeResult(is_valid=True, findings=[])


class _OkWriter:
    meta = PluginMeta(
        name="ok-w", version="0.0.0", description="test", source="built-in"
    )

    def write(self, xml: str, destination: str) -> str:
        return destination


def test_protocols_are_runtime_checkable() -> None:
    """Every Protocol can be checked with ``isinstance`` at runtime."""
    assert isinstance(_OkLoader(), AbstractLoader)
    assert isinstance(_OkValidator(), AbstractValidator)
    assert isinstance(_OkScheme(), AbstractScheme)
    assert isinstance(_OkWriter(), AbstractWriter)


def test_protocols_reject_objects_missing_required_attribute() -> None:
    """A class without ``meta`` is not a structural plugin."""

    class _NotALoader:
        extensions = (".x",)

        def load(self, path):
            return LoaderResult(rows=[], source_hint=path)

        def load_streaming(self, path, chunk_size):
            yield from ()

    # The Protocol check looks for ``meta``; without it the object
    # is not structurally compatible.
    assert not isinstance(_NotALoader(), AbstractLoader)


# ---------------------------------------------------------------------------
# Finding/result dataclasses are immutable and exposable in tools
# ---------------------------------------------------------------------------
def test_validator_finding_is_immutable() -> None:
    """Findings are frozen dataclasses so they can be cached and hashed."""
    from dataclasses import FrozenInstanceError

    finding = ValidatorFinding(
        row_index=0, field="x", rule="R", severity="error", message="."
    )
    with pytest.raises(FrozenInstanceError):
        finding.row_index = 1  # type: ignore[misc]


def test_scheme_finding_records_related_rows() -> None:
    """Cross-record findings carry the related row indices."""
    finding = SchemeFinding(
        row_index=2,
        field=None,
        rule="DUP-CREDITOR-DATE",
        severity="error",
        message="duplicate of row 5.",
        related_rows=(5,),
    )
    assert finding.related_rows == (5,)
    assert finding.remediation is None


# ---------------------------------------------------------------------------
# Registry: built-in registration + lookup
# ---------------------------------------------------------------------------
@pytest.fixture
def fresh_registry() -> PluginRegistry:
    """Isolated registry per test (the global singleton is shared)."""
    return PluginRegistry(PAIN001_API_VERSION)


def test_register_and_lookup_loader_by_name(fresh_registry):
    """Loaders register under their declared name."""
    loader = _OkLoader()
    fresh_registry.register_loader(loader)
    fresh_registry._populated = True  # skip lazy built-in population
    assert fresh_registry.get_loader("ok") is loader


def test_lookup_loader_by_extension(fresh_registry):
    """Loaders dispatch via extension; lookup is case-insensitive."""
    fresh_registry.register_loader(_OkLoader())
    fresh_registry._populated = True
    assert fresh_registry.get_loader_for_extension(".OK") is not None
    assert fresh_registry.get_loader_for_extension(".missing") is None


def test_register_missing_meta_raises(fresh_registry):
    """A plugin without ``PluginMeta`` is refused at registration."""

    class _NoMeta:
        extensions = (".x",)

    with pytest.raises(PluginRegistryError, match="missing a PluginMeta"):
        fresh_registry.register_loader(_NoMeta())  # type: ignore[arg-type]


def test_register_with_newer_api_major_raises(fresh_registry):
    """A plugin targeting a higher API major is refused."""
    bad = _OkLoader()
    bad.meta = PluginMeta(  # type: ignore[misc]
        name="bad",
        version="0",
        description=".",
        api_version=(99, 0),
    )
    with pytest.raises(PluginVersionError, match="upgrade pain001"):
        fresh_registry.register_loader(bad)


def test_register_with_newer_api_minor_warns_but_loads(fresh_registry, caplog):
    """A higher-minor plugin loads with a warning, not a failure."""
    caplog.set_level("WARNING", logger="pain001.plugins.registry")
    ahead = _OkLoader()
    ahead.meta = PluginMeta(  # type: ignore[misc]
        name="ahead",
        version="0",
        description=".",
        api_version=(PAIN001_API_VERSION[0], PAIN001_API_VERSION[1] + 1),
    )
    fresh_registry.register_loader(ahead)
    fresh_registry._populated = True
    assert fresh_registry.get_loader("ahead") is ahead
    assert any(
        "newer plugin methods may be ignored" in r.getMessage()
        for r in caplog.records
    )


def test_register_overrides_built_in_with_log(fresh_registry, caplog):
    """A later registration under the same name wins and is logged."""
    caplog.set_level("INFO", logger="pain001.plugins.registry")
    first = _OkLoader()
    second = _OkLoader()
    fresh_registry.register_loader(first)
    fresh_registry.register_loader(second)
    fresh_registry._populated = True
    assert fresh_registry.get_loader("ok") is second
    assert any("overrides existing" in r.getMessage() for r in caplog.records)


def test_disabled_plugin_skipped(monkeypatch, fresh_registry):
    """``PAIN001_DISABLE_PLUGINS`` skips matching names at registration."""
    monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", "ok, other")
    fresh_registry.reset()  # re-read env
    fresh_registry.register_loader(_OkLoader())
    fresh_registry._populated = True
    assert fresh_registry.get_loader("ok") is None


def test_list_plugins_returns_sorted_info(fresh_registry):
    """``list_plugins`` returns ``PluginInfo`` sorted by (kind, name)."""
    fresh_registry.register_loader(_OkLoader())
    fresh_registry.register_scheme(_OkScheme())
    fresh_registry._populated = True
    infos = fresh_registry.list_plugins()
    assert [(i.kind, i.meta.name) for i in infos] == [
        ("loader", "ok"),
        ("scheme", "ok-s"),
    ]
    assert all(isinstance(i, PluginInfo) for i in infos)


def test_list_plugins_filter_by_kind(fresh_registry):
    """``kind=`` narrows to one plugin kind."""
    fresh_registry.register_loader(_OkLoader())
    fresh_registry.register_validator(_OkValidator())
    fresh_registry._populated = True
    loaders = fresh_registry.list_plugins(kind="loader")
    assert [i.meta.name for i in loaders] == ["ok"]


# ---------------------------------------------------------------------------
# Built-in registration: the singleton registers the five bundled loaders
# ---------------------------------------------------------------------------
def test_global_registry_has_builtins() -> None:
    """The five built-in loaders are discoverable on the singleton."""
    names = {
        info.meta.name for info in global_registry.list_plugins(kind="loader")
    }
    # The .gpg loader (issue #3) will join later; for v0.0.54 we ship five.
    assert {"csv", "json", "jsonl", "sqlite", "parquet"}.issubset(names)


def test_built_in_loader_dispatch_by_extension() -> None:
    """The singleton's extension dispatch resolves the right built-in."""
    csv = global_registry.get_loader_for_extension(".csv")
    sqlite = global_registry.get_loader_for_extension(".sqlite")
    assert csv is not None and csv.meta.name == "csv"
    assert sqlite is not None and sqlite.meta.name == "sqlite"


def test_built_in_loader_meta_marked_built_in() -> None:
    """Built-ins carry ``source=\"built-in\"`` until stamped by an entry point."""
    csv = global_registry.get_loader("csv")
    assert csv is not None
    assert csv.meta.source == "built-in"
    assert csv.meta.api_version == PAIN001_API_VERSION
