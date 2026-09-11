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

"""``scripts/build_corpus.py``: deterministic output and the size budget."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402

from pain001.corpus.registry import SCENARIOS_DIR  # noqa: E402


def test_committed_corpus_is_up_to_date(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--check`` on the tree passes and reports within budget."""
    assert build_corpus.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "up to date" in out and "of 400,000 budget" in out


def _sandbox(tmp_path: Path) -> tuple[Path, Path, list[str]]:
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS_DIR, scenarios)
    data = tmp_path / "data"
    market = data / "market"
    argv = [
        "--scenarios",
        str(scenarios),
        "--market-root",
        str(market),
        "--data-root",
        str(data),
        "--skip-coverage",
    ]
    return scenarios, market, argv


def test_build_writes_then_check_passes_then_detects_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fresh build writes 14 files; a rebuild is a no-op; edits and orphans are caught."""
    scenarios, market, argv = _sandbox(tmp_path)
    assert build_corpus.main(argv + ["--check"]) == 1
    assert "STALE" in capsys.readouterr().out
    assert build_corpus.main(argv) == 0
    out = capsys.readouterr().out
    assert out.count("wrote") == 140 and "35 scenario(s), 140 file(s)" in out
    assert build_corpus.main(argv + ["--check"]) == 0
    assert (
        build_corpus.main(argv) == 0
        and "up to date" in capsys.readouterr().out
    )
    victim = next(market.rglob("*.xml"))
    victim.write_text("<tampered/>", encoding="utf-8")
    orphan = market / "xx" / "orphan.xml"
    orphan.parent.mkdir()
    orphan.write_text("<orphan/>", encoding="utf-8")
    assert build_corpus.main(argv + ["--check"]) == 1
    out = capsys.readouterr().out
    assert "STALE" in out and "ORPHAN" in out and "2 stale or orphaned" in out
    assert build_corpus.main(argv) == 0
    out = capsys.readouterr().out
    assert "removed" in out and not orphan.exists()
    assert "<tampered/>" not in victim.read_text(encoding="utf-8")


def test_budget_breach_and_missing_scenarios(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tiny budget fails the build; an empty scenarios dir fails early."""
    _, _, argv = _sandbox(tmp_path)
    assert build_corpus.main(argv + ["--budget", "10"]) == 1
    assert "exceeds the compressed-size budget" in capsys.readouterr().out
    empty = tmp_path / "none"
    empty.mkdir()
    assert (
        build_corpus.main(["--scenarios", str(empty), "--skip-coverage"]) == 1
    )
    assert "no scenarios" in capsys.readouterr().out


def test_compressed_size_and_relative_paths(tmp_path: Path) -> None:
    """The budget measure sums per-file gzip sizes; paths outside the repo print as-is."""
    (tmp_path / "a.txt").write_text("a" * 10_000)
    assert 0 < build_corpus.compressed_size(tmp_path) < 200
    assert (
        build_corpus._rel(Path("/nonexistent/a.txt")) == "/nonexistent/a.txt"
    )
    assert build_corpus._rel(build_corpus.REPO_ROOT / "x") == "x"


def test_coverage_sets_are_written_beside_the_market_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without --skip-coverage every edition's set and report are written."""
    scenarios, market, argv = _sandbox(tmp_path)
    argv = [a for a in argv if a != "--skip-coverage"] + [
        "--coverage-root",
        str(tmp_path / "data" / "coverage"),
    ]
    assert build_corpus.main(argv) == 0
    out = capsys.readouterr().out
    assert out.count("coverage.json") == 13 and "284 file(s)" in out
    report = json.loads(
        (
            tmp_path
            / "data"
            / "coverage"
            / "pain.001.001.03"
            / "coverage.json"
        ).read_text()
    )
    assert report["complete"] and report["paths"]["declared"] == 954
    assert build_corpus.main(argv + ["--check"]) == 0
