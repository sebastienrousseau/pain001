# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Adapters that surface the existing loaders as plugin instances.

The existing ``pain001.csv``, ``pain001.json``, ``pain001.db``, and
``pain001.parquet`` modules predate the plugin contract; rather than
rewrite them, this module wraps each in a thin
:class:`pain001.plugins.AbstractLoader`-compatible class and
registers it. Internal callers can keep importing the module
functions; external callers go through the registry.

This deliberately exercises the *exact* same surface external
plugins use, so a regression in the contract is caught against the
built-ins before it can hurt a downstream package.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib import metadata

from pain001.plugins._version import PAIN001_API_VERSION
from pain001.plugins.contracts import LoaderResult, PluginMeta


def _pain001_version() -> str:
    """Return the running pain001's installed version (or ``\"0.0.0\"``)."""
    try:
        return metadata.version("pain001")
    except metadata.PackageNotFoundError:  # pragma: no cover - dev install
        return "0.0.0"


def _make_meta(name: str, description: str) -> PluginMeta:
    """Build a :class:`PluginMeta` for a built-in plugin."""
    return PluginMeta(
        name=name,
        version=_pain001_version(),
        description=description,
        api_version=PAIN001_API_VERSION,
        source="built-in",
    )


class _CsvLoader:
    """Built-in CSV loader wrapping :mod:`pain001.csv.load_csv_data`."""

    meta = _make_meta(
        "csv", "Read flat-record payment data from CSV files."
    )
    extensions = (".csv",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire CSV file into a single :class:`LoaderResult`."""
        from pain001.csv.load_csv_data import load_csv_data  # noqa: PLC0415

        rows = load_csv_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_csv_data_streaming``."""
        from pain001.csv.load_csv_data import (  # noqa: PLC0415
            load_csv_data_streaming,
        )

        for chunk in load_csv_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _JsonLoader:
    """Built-in JSON loader wrapping :mod:`pain001.json.load_json_data`."""

    meta = _make_meta(
        "json", "Read flat-record payment data from JSON arrays."
    )
    extensions = (".json",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire JSON document into a single :class:`LoaderResult`."""
        from pain001.json.load_json_data import load_json_data  # noqa: PLC0415

        rows = load_json_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_json_data_streaming``."""
        from pain001.json.load_json_data import (  # noqa: PLC0415
            load_json_data_streaming,
        )

        for chunk in load_json_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _JsonlLoader:
    """Built-in JSONL loader wrapping :mod:`pain001.json.load_json_data`."""

    meta = _make_meta(
        "jsonl",
        "Read flat-record payment data from newline-delimited JSON files.",
    )
    extensions = (".jsonl",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire JSONL stream into a single :class:`LoaderResult`."""
        from pain001.json.load_json_data import load_jsonl_data  # noqa: PLC0415

        rows = load_jsonl_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_jsonl_data_streaming``."""
        from pain001.json.load_json_data import (  # noqa: PLC0415
            load_jsonl_data_streaming,
        )

        for chunk in load_jsonl_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _SqliteLoader:
    """Built-in SQLite loader wrapping :mod:`pain001.db.load_db_data`.

    Reads from the ``pain001`` table; consumers needing a different
    table name should set it via ``--config`` or wrap this loader.
    """

    meta = _make_meta(
        "sqlite",
        "Read flat-record payment data from a SQLite database file.",
    )
    extensions = (".db", ".sqlite")

    def load(self, path: str) -> LoaderResult:
        """Load every row from the ``pain001`` table at ``path``."""
        from pain001.db.load_db_data import load_db_data  # noqa: PLC0415

        rows = load_db_data(path, table_name="pain001")
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_db_data_streaming``."""
        from pain001.db.load_db_data_streaming import (  # noqa: PLC0415
            load_db_data_streaming,
        )

        for chunk in load_db_data_streaming(path, "pain001", chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _ParquetLoader:
    """Built-in Parquet loader (requires the ``pain001[parquet]`` extra)."""

    meta = _make_meta(
        "parquet",
        "Read flat-record payment data from Apache Parquet files "
        "(requires pain001[parquet]).",
    )
    extensions = (".parquet",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire Parquet file into a single :class:`LoaderResult`."""
        from pain001.parquet.load_parquet_data import (  # noqa: PLC0415
            load_parquet_data,
        )

        rows = load_parquet_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_parquet_data_streaming``."""
        from pain001.parquet.load_parquet_data import (  # noqa: PLC0415
            load_parquet_data_streaming,
        )

        for chunk in load_parquet_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


_BUILTIN_LOADERS = (
    _CsvLoader,
    _JsonLoader,
    _JsonlLoader,
    _SqliteLoader,
    _ParquetLoader,
)


def register_all(reg: "PluginRegistry") -> None:  # noqa: F821 - forward ref
    """Register every built-in plugin with ``reg``.

    Called by the registry on first lookup so plugin discovery happens
    lazily. Adding a new built-in loader / scheme / writer means
    extending this function (and adding its adapter class above).

    Args:
        reg: The process-level :class:`PluginRegistry` to populate.
    """
    for cls in _BUILTIN_LOADERS:
        reg.register_loader(cls())
