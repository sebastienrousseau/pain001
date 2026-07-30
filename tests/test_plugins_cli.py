# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Tests for the `pain001 plugins` CLI subcommand group (v0.0.54 #1)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.plugins import LoaderResult, PluginMeta
from pain001.plugins.registry import registry as global_registry


@pytest.fixture
def runner() -> CliRunner:
    """A Click test runner per test."""
    return CliRunner()


def test_plugins_list_renders_table(runner) -> None:
    """The default `pain001 plugins list` prints a table of built-ins."""
    result = runner.invoke(cli, ["plugins", "list"])
    assert result.exit_code == 0, result.output
    assert "Registered plugins" in result.output
    for name in ("csv", "json", "jsonl", "sqlite", "parquet"):
        assert name in result.output


def test_plugins_list_json_emits_each_built_in(runner) -> None:
    """The `--json` flag emits a structured array."""
    result = runner.invoke(cli, ["plugins", "list", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    names = {entry["name"] for entry in payload}
    assert {"csv", "json", "jsonl", "sqlite", "parquet"}.issubset(names)
    csv_entry = next(e for e in payload if e["name"] == "csv")
    assert csv_entry["kind"] == "loader"
    assert csv_entry["source"] == "built-in"
    assert csv_entry["api_version"] == [0, 54]


def test_plugins_list_kind_filter(runner) -> None:
    """`--kind loader` narrows the output to loaders only."""
    result = runner.invoke(
        cli, ["plugins", "list", "--kind", "loader", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload  # at least one loader
    assert all(entry["kind"] == "loader" for entry in payload)


def test_plugins_show_prints_metadata(runner) -> None:
    """`plugins show <name>` prints the four canonical metadata fields."""
    result = runner.invoke(cli, ["plugins", "show", "csv"])
    assert result.exit_code == 0, result.output
    for label in ("source:", "api version:", "description:"):
        assert label in result.output
    assert "csv" in result.output


def test_plugins_show_unknown_exits_one(runner) -> None:
    """A missing plugin exits non-zero with a clear error."""
    result = runner.invoke(cli, ["plugins", "show", "nonexistent-plugin"])
    assert result.exit_code == 1
    assert "No plugin named" in result.output


def test_plugins_show_kind_filter_disambiguates(runner) -> None:
    """`--kind` narrows the show lookup; an unmatched kind is a not-found."""
    result = runner.invoke(cli, ["plugins", "show", "csv", "--kind", "writer"])
    assert result.exit_code == 1
    assert "No plugin named" in result.output


def test_plugins_disable_documents_env_var(runner) -> None:
    """`plugins disable` is documentation-only and prints the env var name."""
    result = runner.invoke(cli, ["plugins", "disable"])
    assert result.exit_code == 0
    assert "PAIN001_DISABLE_PLUGINS" in result.output


def test_plugins_list_reflects_disabled_env(runner, monkeypatch) -> None:
    """A plugin name in `PAIN001_DISABLE_PLUGINS` vanishes from the list."""
    monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", "parquet")
    global_registry.reset()  # re-read env on the next lookup
    try:
        result = runner.invoke(cli, ["plugins", "list", "--json"])
        names = {entry["name"] for entry in json.loads(result.output)}
        assert "parquet" not in names
        assert "csv" in names  # other built-ins unaffected
    finally:
        # Restore the global registry so other tests don't see a hole.
        monkeypatch.delenv("PAIN001_DISABLE_PLUGINS", raising=False)
        global_registry.reset()


# ---------------------------------------------------------------------------
# Plugin fallback path in pain001.data.loader._load_from_file
# ---------------------------------------------------------------------------
class _FakeXlsxLoader:
    """Tiny loader the test injects via the registry to prove fallback."""

    meta = PluginMeta(
        name="xlsx", version="0.0.0", description="test", source="built-in"
    )
    extensions = (".xlsx",)

    def load(self, path: str) -> LoaderResult:
        return LoaderResult(
            rows=[{"id": "INJECTED", "amount": "1.00"}], source_hint=path
        )

    def load_streaming(
        self, path, chunk_size
    ):  # pragma: no cover - unused here
        yield self.load(path)


def test_load_from_file_falls_back_to_plugin_for_unknown_extension(
    tmp_path, monkeypatch
) -> None:
    """An `.xlsx` file is handled by an injected plugin, not the built-in dispatch."""
    fake = tmp_path / "payments.xlsx"
    fake.write_bytes(b"unused-by-the-fake-loader")
    # Stub validate_path so the safety check doesn't reject the synthetic file.
    monkeypatch.setattr(
        "pain001.security.validate_path",
        lambda path, must_exist=True, base_dir=None: str(fake),
    )
    global_registry.reset()
    # Force-populate before injecting so the lazy load doesn't clobber us.
    global_registry._ensure_populated()
    global_registry.register_loader(_FakeXlsxLoader())
    try:
        from pain001.data.loader import _load_from_file

        rows = _load_from_file(str(fake))
        assert rows == [{"id": "INJECTED", "amount": "1.00"}]
    finally:
        global_registry.reset()


def test_load_from_file_unknown_extension_with_no_plugin_raises(
    tmp_path, monkeypatch
) -> None:
    """An unknown extension with no matching plugin raises DataSourceError."""
    fake = tmp_path / "payments.weird"
    fake.write_text("placeholder")
    monkeypatch.setattr(
        "pain001.security.validate_path",
        lambda path, must_exist=True, base_dir=None: str(fake),
    )
    global_registry.reset()
    try:
        from pain001.data.loader import _load_from_file
        from pain001.exceptions import DataSourceError

        with pytest.raises(DataSourceError, match="Unsupported file type"):
            _load_from_file(str(fake))
    finally:
        global_registry.reset()
