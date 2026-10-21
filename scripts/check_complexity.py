#!/usr/bin/env python3
# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Hold every function to the complexity ceilings, against a baseline.

The ceilings are per function: cyclomatic 10 (radon), cognitive 15
(complexipy), Halstead difficulty 30 (radon) and 60 lines, plus 500 lines
per file. Code that was already over a ceiling when the baseline was
taken is recorded in ``complexity-baseline.json`` with the value it had.

The check fails when:

* a function or file that is not in the baseline goes over a ceiling;
* a baselined function or file gets worse on a metric it was over; or
* the baseline is stale, because an offender improved or went away.

The last rule is what makes the baseline a ratchet: it can only shrink,
and every improvement is written down in the change that made it.
``--update`` refuses to run while anything is new or worse, so it can
record an improvement but never absorb a regression. The first
``--update``, with no baseline on disk, records the offenders as found.

Usage:
    python3 scripts/check_complexity.py
    python3 scripts/check_complexity.py --update
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from complexipy import file_complexity
from radon.complexity import cc_visit
from radon.metrics import h_visit

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "complexity-baseline.json"
PATHS = ("pain001", "scripts", "benches", "fuzz", "examples")
#: Runtime scratch space, never source: pytest's basetemp lives here and
#: the package build excludes it the same way.
EXCLUDE = ("pain001/tmp/",)

CEILINGS: dict[str, float] = {
    "cyclomatic": 10,
    "cognitive": 15,
    "halstead": 30,
    "lines": 60,
}
FILE_LINES = 500

Metrics = dict[str, float]
Report = dict[str, Metrics]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _functions(
    node: ast.AST, prefix: str = ""
) -> Iterator[tuple[str, FunctionNode]]:
    """Yield ``(qualname, node)`` for every function under ``node``."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            yield from _functions(child, f"{prefix}{child.name}.")
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualname = f"{prefix}{child.name}"
            yield qualname, child
            yield from _functions(child, f"{qualname}.")


def _cc_blocks(blocks: list[Any]) -> Iterator[Any]:
    """Flatten radon's blocks: methods, closures and nested classes."""
    for block in blocks:
        yield block
        for attribute in ("methods", "closures", "inner_classes"):
            yield from _cc_blocks(list(getattr(block, attribute, [])))


def _halstead(lines: list[str], node: FunctionNode) -> float:
    """Halstead difficulty of one function's own source."""
    segment = textwrap.dedent(
        "".join(lines[node.lineno - 1 : node.end_lineno])
    )
    return round(float(h_visit(segment).total.difficulty), 2)


def measure_file(path: Path) -> Report:
    """Return every metric over its ceiling in ``path``, keyed by name."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    rel = path.relative_to(ROOT).as_posix()
    cyclomatic = {b.lineno: b.complexity for b in _cc_blocks(cc_visit(source))}
    cognitive = {
        f.line_start: f.complexity
        for f in file_complexity(str(path)).functions
    }
    report: Report = {}
    if len(lines) > FILE_LINES:
        report[rel] = {"file_lines": len(lines)}
    for qualname, node in _functions(ast.parse(source)):
        metrics: Metrics = {
            "cyclomatic": cyclomatic.get(node.lineno, 1),
            "cognitive": cognitive.get(node.lineno, 0),
            "halstead": _halstead(lines, node),
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        }
        over = {k: v for k, v in metrics.items() if v > CEILINGS[k]}
        key = f"{rel}::{qualname}"
        while key in report:
            key += "'"
        if over:
            report[key] = over
    return report


def measure() -> Report:
    """Measure every tracked Python file in the repository."""
    report: Report = {}
    for top in PATHS:
        for path in sorted((ROOT / top).rglob("*.py")):
            if path.relative_to(ROOT).as_posix().startswith(EXCLUDE):
                continue
            report.update(measure_file(path))
    return report


def regressions(current: Report, baseline: Report) -> list[str]:
    """Every offender that is new, or worse than its baseline entry."""
    problems: list[str] = []
    for key, metrics in current.items():
        allowed = baseline.get(key, {})
        for metric, value in metrics.items():
            if metric not in allowed:
                problems.append(f"{key}: {metric} {value} is over the ceiling")
            elif value > allowed[metric]:
                problems.append(
                    f"{key}: {metric} rose from {allowed[metric]} to {value}"
                )
    return problems


def improvements(current: Report, baseline: Report) -> list[str]:
    """Every baseline entry the tree now beats, so the baseline is stale."""
    problems: list[str] = []
    for key, metrics in baseline.items():
        for metric, value in metrics.items():
            now = current.get(key, {}).get(metric)
            if now is None or now < value:
                problems.append(
                    f"{key}: {metric} improved from {value} to "
                    f"{now if now is not None else 'within the ceiling'}; "
                    f"run with --update to shrink the baseline"
                )
    return problems


def compare(current: Report, baseline: Report) -> list[str]:
    """Return every way ``current`` breaks the ratchet on ``baseline``."""
    return regressions(current, baseline) + improvements(current, baseline)


def _report(problems: list[str]) -> int:
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1 if problems else 0


def update(current: Report) -> int:
    """Rewrite the baseline, unless that would absorb a regression."""
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        refused = regressions(current, baseline)
        if refused:
            print(
                "refusing to update: the baseline only records "
                "improvements; fix these first:",
                file=sys.stderr,
            )
            return _report(refused)
    text = json.dumps(current, indent=2, sort_keys=True)
    BASELINE.write_text(text + "\n", encoding="utf-8")
    print(f"baseline: {len(current)} offenders written")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Check the tree against the baseline, or rewrite it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update", action="store_true", help="record an improvement"
    )
    args = parser.parse_args(argv)
    current = measure()
    if args.update:
        return update(current)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if _report(compare(current, baseline)):
        return 1
    print(f"complexity: {len(current)} baselined offenders, none worse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
