# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Benchmark evidence must fail closed and enumerate executable workloads."""

import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from benches import bench_features

ROOT = Path(__file__).resolve().parents[1]


def test_measure_preserves_failure_diagnostics(monkeypatch):
    """A failed assertion cannot be converted into a successful timing."""
    monkeypatch.setattr(
        bench_features.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2, stdout="output", stderr="failure"
        ),
    )
    with pytest.raises(
        RuntimeError, match=r"demo.py failed \(2\):\noutput\nfailure"
    ):
        bench_features.measure(Path("demo.py"))


def test_measure_propagates_timeout(monkeypatch):
    """Hung examples fail the benchmark instead of returning partial evidence."""

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("example", 180)

    monkeypatch.setattr(bench_features.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        bench_features.measure(Path("demo.py"))


def test_measure_uses_current_interpreter_and_records_elapsed(monkeypatch):
    """The measured process uses the same installed extras as verification."""
    calls = []

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    times = iter([10.0, 12.5])
    monkeypatch.setattr(bench_features.subprocess, "run", run)
    monkeypatch.setattr(
        bench_features.time, "perf_counter", lambda: next(times)
    )
    assert bench_features.measure(Path("demo.py")) == {
        "example": "demo.py",
        "seconds": 2.5,
    }
    assert calls[0][0] == ([bench_features.sys.executable, "demo.py"],)
    assert calls[0][1]["cwd"] == bench_features.ROOT
    assert calls[0][1]["timeout"] == 180


def test_runner_requires_examples(monkeypatch, tmp_path):
    """An empty checkout must not produce a misleading green report."""
    monkeypatch.setattr(bench_features, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="No executable"):
        bench_features.main()


def test_runner_includes_every_numbered_example(monkeypatch, capsys):
    """New examples enter the benchmark without a second hand-kept list."""
    monkeypatch.setattr(
        bench_features,
        "measure",
        lambda path: {"example": path.name, "seconds": 1.0},
    )
    bench_features.main()
    report = json.loads(capsys.readouterr().out)
    assert report["python"] and report["platform"]
    assert [sample["example"] for sample in report["samples"]] == [
        path.name for path in sorted((ROOT / "examples").glob("[0-9]*.py"))
    ]


def test_feature_evidence_paths_and_examples_are_current():
    """The evidence map names real files and includes every runnable example."""
    document = (ROOT / "docs/verification-coverage.md").read_text(
        encoding="utf-8"
    )
    references = set(re.findall(r"`((?:tests|examples)/[^`]+\.py)`", document))
    assert references
    for reference in references:
        assert (ROOT / reference).is_file(), reference
    assert {
        str(path.relative_to(ROOT))
        for path in (ROOT / "examples").glob("[0-9]*.py")
    } <= references
