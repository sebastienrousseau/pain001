# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Coverage closers for `pain001.plugins._builtins` and `.registry`.

The contract test suite (`test_plugins_contract.py`) and the CLI suite
(`test_plugins_cli.py`) cover the public Protocol surface and the
operator-facing entry points. This file fills the remaining branches:
each built-in adapter's load + streaming methods, every
get_*/register_* path on the registry, the entry-point discovery
shim, and the `_stamp_source` mutation hook.
"""

from __future__ import annotations

import json
import sqlite3
from importlib.metadata import EntryPoint
from unittest.mock import MagicMock, patch

import pytest

from pain001.plugins import (
    PAIN001_API_VERSION,
    LoaderResult,
    PluginMeta,
    SchemeResult,
    ValidatorResult,
)
from pain001.plugins._builtins import (
    _CsvLoader,
    _JsonlLoader,
    _JsonLoader,
    _ParquetLoader,
    _SqliteLoader,
    register_all,
)
from pain001.plugins.registry import (
    PluginRegistry,
    _iter_entry_points,
    _load_entry_point_plugins,
    _register_by_kind,
    _stamp_source,
)


# ---------------------------------------------------------------------------
# Built-in loaders: real load() + load_streaming() per adapter
# ---------------------------------------------------------------------------
@pytest.fixture
def csv_file(tmp_path):
    """A two-row CSV the CsvLoader can parse."""
    path = tmp_path / "rows.csv"
    path.write_text("id,amount\nA,1.00\nB,2.00\n")
    return str(path)


@pytest.fixture
def json_file(tmp_path):
    """A two-record JSON array the JsonLoader can parse."""
    path = tmp_path / "rows.json"
    path.write_text(json.dumps([{"id": "A"}, {"id": "B"}]))
    return str(path)


@pytest.fixture
def jsonl_file(tmp_path):
    """A two-line JSONL file the JsonlLoader can parse."""
    path = tmp_path / "rows.jsonl"
    path.write_text(
        json.dumps({"id": "A"}) + "\n" + json.dumps({"id": "B"}) + "\n"
    )
    return str(path)


@pytest.fixture
def sqlite_file(tmp_path):
    """A SQLite database with a `pain001` table the SqliteLoader can read."""
    path = tmp_path / "rows.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE pain001 (id TEXT, amount REAL)")
    conn.executemany(
        "INSERT INTO pain001 VALUES (?, ?)", [("A", 1.0), ("B", 2.0)]
    )
    conn.commit()
    conn.close()
    return str(path)


def test_csv_loader_load(csv_file):
    """CsvLoader.load returns a LoaderResult with rows + source hint."""
    res = _CsvLoader().load(csv_file)
    assert isinstance(res, LoaderResult)
    assert res.source_hint == csv_file
    assert len(res.rows) == 2


def test_csv_loader_load_streaming(csv_file):
    """CsvLoader.load_streaming yields LoaderResult chunks."""
    chunks = list(_CsvLoader().load_streaming(csv_file, chunk_size=1))
    assert chunks
    assert all(isinstance(c, LoaderResult) for c in chunks)


def test_json_loader_load(json_file):
    """JsonLoader.load round-trips a JSON array into LoaderResult.rows."""
    res = _JsonLoader().load(json_file)
    assert len(res.rows) == 2


def test_json_loader_load_streaming(json_file):
    """JsonLoader.load_streaming yields at least one chunk."""
    chunks = list(_JsonLoader().load_streaming(json_file, chunk_size=10))
    assert chunks


def test_jsonl_loader_load(jsonl_file):
    """JsonlLoader.load returns one row per JSONL line."""
    res = _JsonlLoader().load(jsonl_file)
    assert len(res.rows) == 2


def test_jsonl_loader_load_streaming(jsonl_file):
    """JsonlLoader.load_streaming yields at least one chunk."""
    chunks = list(_JsonlLoader().load_streaming(jsonl_file, chunk_size=10))
    assert chunks


def test_sqlite_loader_load(sqlite_file):
    """SqliteLoader.load reads from the `pain001` table."""
    res = _SqliteLoader().load(sqlite_file)
    assert len(res.rows) == 2


def test_sqlite_loader_load_streaming(sqlite_file):
    """SqliteLoader.load_streaming yields at least one chunk."""
    chunks = list(_SqliteLoader().load_streaming(sqlite_file, chunk_size=10))
    assert chunks


def test_parquet_loader_load_calls_underlying_function():
    """ParquetLoader.load delegates to pain001.parquet.load_parquet_data."""
    with patch(
        "pain001.parquet.load_parquet_data.load_parquet_data",
        return_value=[{"id": "A"}],
    ) as stub:
        res = _ParquetLoader().load("/tmp/fake.parquet")
    stub.assert_called_once_with("/tmp/fake.parquet")
    assert res.rows == [{"id": "A"}]


def test_parquet_loader_streaming_calls_underlying_function():
    """ParquetLoader.load_streaming delegates to ...load_parquet_data_streaming."""
    with patch(
        "pain001.parquet.load_parquet_data.load_parquet_data_streaming",
        return_value=iter([[{"id": "A"}], [{"id": "B"}]]),
    ) as stub:
        chunks = list(
            _ParquetLoader().load_streaming("/tmp/fake.parquet", chunk_size=1)
        )
    stub.assert_called_once_with("/tmp/fake.parquet", 1)
    assert len(chunks) == 2


def test_register_all_registers_five_built_in_loaders():
    """register_all populates the registry with every bundled loader."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    register_all(reg)
    reg._populated = True
    names = {info.meta.name for info in reg.list_plugins(kind="loader")}
    assert {"csv", "json", "jsonl", "sqlite", "parquet"}.issubset(names)


# ---------------------------------------------------------------------------
# Registry: every public lookup, every register_* path
# ---------------------------------------------------------------------------
def _meta(name: str) -> PluginMeta:
    return PluginMeta(
        name=name, version="0", description=".", source="built-in"
    )


class _V:
    meta = _meta("v1")

    def validate(self, rows, *, message_type):
        return ValidatorResult(is_valid=True, findings=[])


class _S:
    meta = _meta("s1")

    def validate(self, rows, *, message_type):
        return SchemeResult(is_valid=True, findings=[])


class _W:
    meta = _meta("w1")

    def write(self, xml, destination):
        return destination


def test_get_validator_returns_none_when_missing():
    """get_validator returns None for an unregistered name."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    reg._populated = True
    assert reg.get_validator("nope") is None


def test_get_scheme_returns_none_when_missing():
    """get_scheme returns None for an unregistered name."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    reg._populated = True
    assert reg.get_scheme("nope") is None


def test_get_writer_returns_none_when_missing():
    """get_writer returns None for an unregistered name."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    reg._populated = True
    assert reg.get_writer("nope") is None


def test_register_and_lookup_validator():
    """register_validator + get_validator round-trip."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    v = _V()
    reg.register_validator(v)
    reg._populated = True
    assert reg.get_validator("v1") is v


def test_register_and_lookup_scheme():
    """register_scheme + get_scheme round-trip."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    s = _S()
    reg.register_scheme(s)
    reg._populated = True
    assert reg.get_scheme("s1") is s


def test_register_and_lookup_writer():
    """register_writer + get_writer round-trip."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    w = _W()
    reg.register_writer(w)
    reg._populated = True
    assert reg.get_writer("w1") is w


def test_get_loader_returns_none_when_missing():
    """get_loader returns None for an unregistered name."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    reg._populated = True
    assert reg.get_loader("nope") is None


# ---------------------------------------------------------------------------
# Entry-point discovery + _stamp_source mutation
# ---------------------------------------------------------------------------
def test_iter_entry_points_returns_iterable_for_known_group():
    """The helper accepts a group name and returns an iterable."""
    eps = list(_iter_entry_points("pain001.loaders"))
    # Iterable; empty when no third-party plugins are installed.
    assert isinstance(eps, list)


def test_stamp_source_replaces_built_in_with_dist_name():
    """_stamp_source rewrites meta.source to the entry-point dist name."""
    plugin = _V()
    # Build a fake EntryPoint with a dist attribute.
    fake_dist = MagicMock(name="dist")
    fake_dist.name = "fake-pkg"
    fake_dist.version = "9.9.9"
    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.dist = fake_dist
    fake_ep.name = "fake-name"
    _stamp_source(plugin, fake_ep)
    assert plugin.meta.source == "fake-pkg==9.9.9"
    assert plugin.meta.name == "v1"  # unchanged


def test_stamp_source_falls_back_to_entry_point_name_when_dist_missing():
    """_stamp_source uses the entry-point name as a last resort."""
    plugin = _V()
    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.dist = None
    fake_ep.name = "ep-name-only"
    _stamp_source(plugin, fake_ep)
    assert plugin.meta.source == "ep-name-only==?"


def test_register_by_kind_dispatches_each_kind():
    """_register_by_kind routes plugins into the right per-kind store."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    v, s, w = _V(), _S(), _W()
    _register_by_kind(reg, v, "validator")
    _register_by_kind(reg, s, "scheme")
    _register_by_kind(reg, w, "writer")
    reg._populated = True
    assert reg.get_validator("v1") is v
    assert reg.get_scheme("s1") is s
    assert reg.get_writer("w1") is w


def test_register_by_kind_dispatches_loader():
    """_register_by_kind routes a loader into the loader store too."""
    reg = PluginRegistry(PAIN001_API_VERSION)

    class _L:
        meta = _meta("loader-x")
        extensions = (".x",)

        def load(self, path):
            return LoaderResult(rows=[], source_hint=path)

        def load_streaming(self, path, chunk_size):
            yield self.load(path)

    loader = _L()
    _register_by_kind(reg, loader, "loader")
    reg._populated = True
    assert reg.get_loader("loader-x") is loader


def test_load_entry_point_plugins_skips_broken_plugin(caplog):
    """A plugin raising at instantiation is logged + skipped, not propagated."""
    reg = PluginRegistry(PAIN001_API_VERSION)

    class _BoomEntry:
        name = "boom"
        dist = None

        def load(self):
            raise RuntimeError("broken plugin")

    with patch(
        "pain001.plugins.registry._iter_entry_points",
        side_effect=lambda group: (
            [_BoomEntry()] if group == "pain001.loaders" else []
        ),
    ):
        caplog.set_level("WARNING", logger="pain001.plugins.registry")
        _load_entry_point_plugins(reg)
    assert any(
        "skipping loader plugin from entry-point boom" in r.getMessage()
        for r in caplog.records
    )


def test_load_entry_point_plugins_registers_a_working_plugin():
    """A clean entry point loads, gets stamped, and ends up in the registry."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    reg._populated = True  # don't trigger lazy built-in load

    class _GoodEntry:
        name = "good"
        dist = MagicMock()

        def __init__(self) -> None:
            self.dist.name = "good-pkg"
            self.dist.version = "1.2.3"

        def load(self):
            return _V

    with patch(
        "pain001.plugins.registry._iter_entry_points",
        side_effect=lambda group: (
            [_GoodEntry()] if group == "pain001.validators" else []
        ),
    ):
        _load_entry_point_plugins(reg)
    plugin = reg.get_validator("v1")
    assert plugin is not None
    assert plugin.meta.source == "good-pkg==1.2.3"
