# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The complexity gate catches each ceiling and only ever shrinks."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """The gate as a module, measuring and writing in a scratch directory.

    Not ``tmp_path``: pytest's basetemp is under ``pain001/tmp`` here,
    and the deliberately complex, untyped Python these tests write
    would then sit inside the package tree, where ``mypy pain001``
    reads it.
    """
    spec = importlib.util.spec_from_file_location(
        "check_complexity", ROOT / "scripts" / "check_complexity.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="pain001-complexity-") as raw:
        scratch = Path(raw)
        monkeypatch.setattr(module, "ROOT", scratch)
        monkeypatch.setattr(module, "PATHS", ("src",))
        monkeypatch.setattr(module, "BASELINE", scratch / "baseline.json")
        (scratch / "src").mkdir()
        yield module


def _branchy() -> str:
    body = "".join(
        f"    if x == {i}:\n        return {i}\n" for i in range(11)
    )
    return f"def branchy(x):\n{body}    return -1\n"


def _nested() -> str:
    return (
        "def nested(a, b, c, d):\n"
        "    for i in a:\n"
        "        if i:\n"
        "            for j in b:\n"
        "                if j:\n"
        "                    while c:\n"
        "                        if d:\n"
        "                            return 1\n"
        "    return 0\n"
    )


def _long() -> str:
    body = "".join(f"    y{i} = {i}\n" for i in range(60))
    return f"def long():\n{body}    return 0\n"


def _difficult() -> str:
    # Halstead difficulty is (distinct operators / 2) * (operands /
    # distinct operands): one operand under twelve operators.
    ops = ["+", "-", "*", "/", "//", "%", "**", "<<", ">>", "&", "|", "^"]
    body = "".join(f"    c = c {op} c\n" for op in ops * 2)
    return f"def difficult(c):\n{body}    return c\n"


def _write(gate: ModuleType, source: str) -> Path:
    path = gate.ROOT / "src" / "offender.py"
    path.write_text(source, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("source", "key", "metric"),
    [
        (_branchy(), "src/offender.py::branchy", "cyclomatic"),
        (_nested(), "src/offender.py::nested", "cognitive"),
        (_long(), "src/offender.py::long", "lines"),
        (_difficult(), "src/offender.py::difficult", "halstead"),
        ("x = 1\n" * 501, "src/offender.py", "file_lines"),
    ],
    ids=["cyclomatic", "cognitive", "lines", "halstead", "file-lines"],
)
def test_each_ceiling_is_caught(
    gate: ModuleType, source: str, key: str, metric: str
) -> None:
    report = gate.measure_file(_write(gate, source))
    assert metric in report[key], report


def test_methods_are_measured_by_qualified_name(gate: ModuleType) -> None:
    source = "class Box:\n" + "".join(
        "    " + line + "\n" for line in _branchy().splitlines()
    )
    report = gate.measure_file(_write(gate, source))
    assert "src/offender.py::Box.branchy" in report


def test_a_new_offender_fails(gate: ModuleType) -> None:
    problems = gate.compare({"a.py::f": {"cyclomatic": 12}}, {})
    assert problems == ["a.py::f: cyclomatic 12 is over the ceiling"]


def test_a_baselined_offender_that_rises_fails(gate: ModuleType) -> None:
    problems = gate.compare(
        {"a.py::f": {"cyclomatic": 13}}, {"a.py::f": {"cyclomatic": 12}}
    )
    assert problems == ["a.py::f: cyclomatic rose from 12 to 13"]


def test_an_improvement_makes_the_baseline_stale(gate: ModuleType) -> None:
    problems = gate.compare({}, {"a.py::f": {"cyclomatic": 12}})
    assert len(problems) == 1
    assert "improved from 12 to within the ceiling" in problems[0]


def test_update_records_an_improvement(gate: ModuleType) -> None:
    gate.BASELINE.write_text(
        json.dumps({"src/gone.py::f": {"cyclomatic": 12}}), encoding="utf-8"
    )
    assert gate.main(["--update"]) == 0
    assert json.loads(gate.BASELINE.read_text(encoding="utf-8")) == {}


def test_update_refuses_to_absorb_a_regression(
    gate: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    gate.BASELINE.write_text("{}", encoding="utf-8")
    _write(gate, _branchy())
    assert gate.main(["--update"]) == 1
    assert "refusing to update" in capsys.readouterr().err
    assert gate.BASELINE.read_text(encoding="utf-8") == "{}"


def test_first_update_records_what_it_finds(gate: ModuleType) -> None:
    _write(gate, _branchy())
    assert gate.main(["--update"]) == 0
    baseline = json.loads(gate.BASELINE.read_text(encoding="utf-8"))
    assert "src/offender.py::branchy" in baseline


def test_scratch_space_is_not_measured(gate: ModuleType) -> None:
    """pytest's basetemp sits under pain001/tmp; it is not source."""
    scratch = gate.ROOT / "pain001" / "tmp"
    scratch.mkdir(parents=True)
    (scratch / "offender.py").write_text(_branchy(), encoding="utf-8")
    gate.PATHS = ("pain001",)
    assert gate.measure() == {}


def test_check_fails_on_a_new_offender(gate: ModuleType) -> None:
    gate.BASELINE.write_text("{}", encoding="utf-8")
    _write(gate, _branchy())
    assert gate.main([]) == 1


def test_check_passes_within_the_baseline(
    gate: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    gate.BASELINE.write_text("{}", encoding="utf-8")
    _write(gate, "def fine():\n    return 1\n")
    assert gate.main([]) == 0
    assert "none worse" in capsys.readouterr().out


def test_the_tree_matches_its_baseline() -> None:
    """The committed baseline is exactly what the tree measures."""
    spec = importlib.util.spec_from_file_location(
        "check_complexity_tree", ROOT / "scripts" / "check_complexity.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main([]) == 0
