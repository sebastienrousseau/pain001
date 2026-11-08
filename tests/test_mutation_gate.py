# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The fast mutation tier runs as shards and is gated as one score."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
_TIER_PACKAGES = ("xml", "security", "config", "templates")


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mutation_gate", ROOT / "scripts" / "mutation_gate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, **stats: int) -> str:
    path.write_text(json.dumps(stats), encoding="utf-8")
    return str(path)


def _make_patterns(variable: str) -> list[str]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(rf"^{variable} = (.+)$", text, re.MULTILINE)
    assert match, f"{variable} is not set in the Makefile"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_the_score_sums_every_shard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _write(tmp_path / "a.json", killed=90, survived=10, timeout=2)
    second = _write(tmp_path / "b.json", killed=10, survived=10, no_tests=1)
    gate = _gate()
    assert (
        gate.main(["--floor", "80", "--stats", first, "--stats", second]) == 0
    )
    out = capsys.readouterr().out
    assert "83.3% (100 of 120 checked" in out
    assert "1 unreached, 2 timed out" in out
    assert (
        gate.main(["--floor", "84", "--stats", first, "--stats", second]) == 1
    )


def test_a_missing_shard_fails_the_gate(tmp_path: Path) -> None:
    present = _write(tmp_path / "a.json", killed=1, survived=0)
    assert (
        _gate().main(
            [
                "--floor",
                "0",
                "--stats",
                present,
                "--stats",
                str(tmp_path / "b"),
            ]
        )
        == 1
    )


def test_every_fast_tier_module_is_in_exactly_one_shard() -> None:
    """A module the shard patterns miss would never be mutated in CI."""
    registry = _make_patterns("MUTATION_SHARD_REGISTRY")
    rest = _make_patterns("MUTATION_SHARD_REST")
    package = ROOT / "pain001"
    modules = [
        ".".join(path.relative_to(ROOT).with_suffix("").parts)
        for name in _TIER_PACKAGES
        for path in (package / name).rglob("*.py")
        if path.name != "__init__.py"
    ]
    assert modules
    for module in modules:
        mutant = f"{module}.x_function__mutmut_1"
        hits = [
            shard
            for shard, patterns in (("registry", registry), ("rest", rest))
            if any(fnmatch.fnmatch(mutant, p) for p in patterns)
        ]
        assert len(hits) == 1, f"{module} is in shards {hits}"
