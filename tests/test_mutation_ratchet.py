# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Surviving mutants are held to a per-function baseline that only shrinks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ratchet() -> ModuleType:
    """Load scripts/mutation_ratchet.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "mutation_ratchet", ROOT / "scripts" / "mutation_ratchet.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _survivors(path: Path, *names: str) -> Path:
    """Write a survivors.txt in mutmut's ``results`` layout."""
    path.write_text(
        "".join(f"    {n}: survived\n" for n in names) + "\n", encoding="utf-8"
    )
    return path


def _baseline(path: Path, functions: dict[str, int]) -> Path:
    """Write a baseline file with the given per-function counts."""
    payload = {"score": "x", "survivors": 0, "functions": functions}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_a_line_names_its_function() -> None:
    """The mutant number goes; module, class and method stay."""
    fn = _ratchet().function_of
    assert fn("    pain001.a.x_f__mutmut_12: survived") == "pain001.a.x_f"
    assert fn("pain001.a.xǁCǁm__mutmut_1: survived") == "pain001.a.xǁCǁm"
    assert fn("pain001.a.x_f__mutmut_x__mutmut_2: survived") == (
        "pain001.a.x_f__mutmut_x"
    )
    assert fn("   ") is None


@pytest.mark.parametrize(
    "line",
    ["pain001.a.x_f__mutmut_1: killed", "pain001.a.x_f: survived", "junk"],
)
def test_a_line_that_is_not_a_survivor_is_refused(line: str) -> None:
    """Anything but a survivor entry is an error, not silently skipped."""
    with pytest.raises(ValueError, match="not a survivor line"):
        _ratchet().function_of(line)


def test_survivors_sum_per_function_across_shards(tmp_path: Path) -> None:
    """Two shards' lists add up per function."""
    a = _survivors(tmp_path / "a.txt", "m.x_f__mutmut_1", "m.x_f__mutmut_2")
    b = _survivors(tmp_path / "b.txt", "m.x_f__mutmut_3", "n.x_g__mutmut_1")
    counts = _ratchet().count_survivors([a, b])
    assert counts == {"m.x_f": 3, "n.x_g": 1}


def test_compare_flags_worse_new_and_better() -> None:
    """More than recorded, or any in an unlisted function, is worse."""
    from collections import Counter

    worse, better = _ratchet().compare(
        {"a": 2, "b": 3, "c": 1}, Counter({"a": 2, "b": 4, "d": 1})
    )
    assert worse == [
        "b: 4 survivors, baseline 3",
        "d: 1 survivors, baseline 0",
    ]
    assert better == ["c: 0 survivors, baseline 1"]


def test_main_passes_at_or_under_the_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Equal or fewer survivors pass, and improvements are listed."""
    base = _baseline(tmp_path / "b.json", {"m.x_f": 2, "m.x_g": 1})
    lst = _survivors(tmp_path / "s.txt", "m.x_f__mutmut_1")
    code = _ratchet().main(["--baseline", str(base), "--survivors", str(lst)])
    out = capsys.readouterr().out
    assert code == 0
    assert "  better: m.x_f: 1 survivors, baseline 2" in out
    assert "  better: m.x_g: 0 survivors, baseline 1" in out
    assert out.endswith(
        "mutation ratchet: 1 survivors in 1 functions (baseline 3); "
        "0 worse, 2 better\n"
    )
    assert json.loads(base.read_text())["functions"] == {
        "m.x_f": 2,
        "m.x_g": 1,
    }


def test_main_fails_on_a_regression(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One more survivor than recorded fails the run."""
    base = _baseline(tmp_path / "b.json", {"m.x_f": 1})
    lst = _survivors(tmp_path / "s.txt", "m.x_f__mutmut_1", "m.x_f__mutmut_2")
    code = _ratchet().main(["--baseline", str(base), "--survivors", str(lst)])
    assert code == 1
    assert "  worse: m.x_f: 2 survivors, baseline 1" in capsys.readouterr().out


def test_update_records_an_improvement(tmp_path: Path) -> None:
    """--update rewrites the counts, sorted, with the score given."""
    base = _baseline(tmp_path / "b.json", {"m.x_g": 2, "m.x_f": 5})
    lst = _survivors(tmp_path / "s.txt", "m.x_g__mutmut_1", "m.x_f__mutmut_9")
    args = ["--baseline", str(base), "--survivors", str(lst), "--update"]
    assert _ratchet().main([*args, "--score", "85.3%"]) == 0
    text = base.read_text(encoding="utf-8")
    assert json.loads(text) == {
        "score": "85.3%",
        "survivors": 2,
        "functions": {"m.x_f": 1, "m.x_g": 1},
    }
    assert text.index('"m.x_f"') < text.index('"m.x_g"')
    assert text.endswith("}\n")


def test_update_refuses_a_regression(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--update never absorbs a worse count; the file is left alone."""
    base = _baseline(tmp_path / "b.json", {})
    before = base.read_text(encoding="utf-8")
    lst = _survivors(tmp_path / "s.txt", "m.x_f__mutmut_1")
    args = ["--baseline", str(base), "--survivors", str(lst), "--update"]
    assert _ratchet().main(args) == 1
    assert "refusing to record a regression" in capsys.readouterr().err
    assert base.read_text(encoding="utf-8") == before


def test_the_first_update_records_what_it_finds(tmp_path: Path) -> None:
    """With no baseline on disk, --update writes the current counts."""
    base = tmp_path / "new.json"
    lst = _survivors(tmp_path / "s.txt")
    args = ["--baseline", str(base), "--survivors", str(lst), "--update"]
    assert _ratchet().main(args) == 0
    assert json.loads(base.read_text()) == {
        "score": None,
        "survivors": 0,
        "functions": {},
    }


def test_a_missing_survivor_list_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A shard that uploaded nothing cannot pass as zero survivors."""
    base = _baseline(tmp_path / "b.json", {})
    gone = tmp_path / "missing.txt"
    code = _ratchet().main(["--baseline", str(base), "--survivors", str(gone)])
    assert code == 1
    assert f"no survivor list at {gone}" in capsys.readouterr().err
