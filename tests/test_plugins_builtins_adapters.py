# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Built-in loader, scheme and metadata adapters, run directly.

The adapters are registered once at import, so a test that only goes
through the process-wide registry never re-runs their construction.
These tests build fresh instances and read every file format through
both the whole-file and the streaming entry points.
"""

from __future__ import annotations

import json
import shutil
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.plugins import _builtins
from pain001.plugins._version import PAIN001_API_VERSION, _pain001_version
from pain001.plugins.contracts import PluginMeta
from pain001.validation._scheme_rules import PROFILES
from pain001.validation.rails import DESCRIPTIONS

SAMPLE_DIR = TEMPLATES_DIR / "pain.001.001.03"


@pytest.fixture
def sources(tmp_path: Path) -> dict[str, str]:
    """Write the four-row sample batch in every built-in format."""
    rows = load_csv_data(str(SAMPLE_DIR / "template.csv"))
    assert len(rows) == 4
    paths = {
        "csv": tmp_path / "batch.csv",
        "json": tmp_path / "batch.json",
        "jsonl": tmp_path / "batch.jsonl",
        "sqlite": tmp_path / "batch.db",
        "parquet": tmp_path / "batch.parquet",
    }
    shutil.copy(SAMPLE_DIR / "template.csv", paths["csv"])
    shutil.copy(SAMPLE_DIR / "template.db", paths["sqlite"])
    paths["json"].write_text(json.dumps(rows), encoding="utf-8")
    paths["jsonl"].write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    pa = import_module("pyarrow")
    import_module("pyarrow.parquet").write_table(
        pa.Table.from_pylist(rows), paths["parquet"]
    )
    return {name: str(path) for name, path in paths.items()}


LOADERS: dict[str, Any] = {
    "csv": _builtins._CsvLoader,
    "json": _builtins._JsonLoader,
    "jsonl": _builtins._JsonlLoader,
    "sqlite": _builtins._SqliteLoader,
    "parquet": _builtins._ParquetLoader,
}


@pytest.mark.parametrize("fmt", sorted(LOADERS))
def test_load_returns_every_row_tagged_with_path(
    fmt: str, sources: dict[str, str]
) -> None:
    """``load`` reads the whole file and cites it as the source."""
    result = LOADERS[fmt]().load(sources[fmt])
    assert result.source_hint == sources[fmt]
    assert [row["payment_id"] for row in result.rows] == [
        row["payment_id"]
        for row in load_csv_data(str(SAMPLE_DIR / "template.csv"))
    ]


@pytest.mark.parametrize("fmt", sorted(LOADERS))
def test_load_streaming_honours_chunk_size(
    fmt: str, sources: dict[str, str]
) -> None:
    """Streaming yields ``chunk_size`` rows at a time, each tagged."""
    chunks = list(LOADERS[fmt]().load_streaming(sources[fmt], 3))
    assert [len(chunk.rows) for chunk in chunks] == [3, 1]
    assert {chunk.source_hint for chunk in chunks} == {sources[fmt]}


def test_make_meta_describes_a_built_in() -> None:
    """Built-in metadata carries the running version and API."""
    assert _builtins._make_meta("n", "Desc.") == PluginMeta(
        name="n",
        version=_pain001_version(),
        description="Desc.",
        api_version=PAIN001_API_VERSION,
        source="built-in",
    )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("got X", "got X."),
        ("done.", "done."),
        ("why?  ", "why?"),
        ("wow!", "wow!"),
        ("", ""),
    ],
)
def test_as_sentence_terminates_once(message: str, expected: str) -> None:
    """Messages end in exactly one sentence terminator."""
    assert _builtins._as_sentence(message) == expected


def test_profile_scheme_keeps_description_and_legacy_result() -> None:
    """The adapter exposes its blurb and the profile's own result."""
    marker = object()
    profile = SimpleNamespace(name="p", validate=lambda rows: marker)
    scheme = _builtins._ProfileScheme(profile, "A blurb.")
    assert scheme.meta.description == "A blurb."
    assert scheme.meta.name == "p"
    assert scheme.validate_legacy([]) is marker


class _Recorder:
    """Registry stand-in that records what ``register_all`` hands it."""

    def __init__(self) -> None:
        """Start with no registrations."""
        self.loaders: list[Any] = []
        self.schemes: dict[str, Any] = {}
        self.writers: list[Any] = []

    def register_loader(self, loader: Any) -> None:
        """Record a loader."""
        self.loaders.append(loader)

    def register_scheme(self, scheme: Any) -> None:
        """Record a scheme by name."""
        self.schemes[scheme.meta.name] = scheme

    def register_validator(self, validator: Any) -> None:
        """Accept a validator (none are built in)."""

    def register_writer(self, writer: Any) -> None:
        """Record a writer."""
        self.writers.append(writer)

    def get_loader_for_extension(self, extension: str) -> Any:
        """Return no loader."""
        return None


def test_register_all_describes_every_scheme() -> None:
    """Bundled profiles use their blurb; rail profiles the rail text."""
    recorder = _Recorder()
    _builtins.register_all(recorder)
    assert set(recorder.schemes) == set(PROFILES)
    for name, scheme in recorder.schemes.items():
        expected = (
            _builtins._SCHEME_DESCRIPTIONS.get(name) or DESCRIPTIONS[name]
        )
        assert scheme.meta.description == expected, name
    assert recorder.schemes["sepa-sct"].meta.description.startswith("SEPA")
    assert [w.meta.name for w in recorder.writers] == ["xml-file"]
    assert {"csv", "json", "jsonl", "sqlite", "parquet"} <= {
        loader.meta.name for loader in recorder.loaders
    }
