#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Hold surviving mutants to a baseline that may only shrink.

The weekly full mutation run writes ``mutants/survivors.txt`` in each
shard: one ``<module>.<function>__mutmut_<n>: survived`` line per mutant
the tests let through. This script sums them per function and compares
the sums with ``mutation-baseline.json``. It fails when:

* a function has more survivors than the baseline records; or
* a function the baseline does not list has any survivors (its
  baseline is zero).

Counting per function, not per mutant, keeps the baseline stable when a
function changes: mutmut renumbers a function's mutants whenever its
body changes, but the count of the ones the tests miss only goes up if
the tests got weaker or the new code is untested.

A function with fewer survivors than recorded is an improvement. It is
reported, not failed, because the baseline can only be rewritten from a
full run's artifacts; ``--update`` writes the new counts and refuses to
run while anything is worse, so it records improvements and never
absorbs a regression. The first ``--update``, with no baseline on disk,
records the survivors as found; a plain check with no baseline fails.
The ``score`` field is informational.

The standard library only, so the gate job needs no virtualenv.

Usage:
    python3 scripts/mutation_ratchet.py --baseline mutation-baseline.json \\
        --survivors shard1/survivors.txt --survivors shard2/survivors.txt
    ... --update
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

SUFFIX = ": survived"


def function_of(line: str) -> str | None:
    """The function a ``survivors.txt`` line names, or ``None`` if blank.

    Args:
        line: One line, such as ``pain001.x.x_f__mutmut_3: survived``.

    Returns:
        ``pain001.x.x_f`` (class methods keep mutmut's ``xǁCǁm`` form).

    Raises:
        ValueError: The line is not a survivor entry.
    """
    text = line.strip()
    if not text:
        return None
    if not text.endswith(SUFFIX) or "__mutmut_" not in text:
        raise ValueError(f"not a survivor line: {text!r}")
    return text[: -len(SUFFIX)].rsplit("__mutmut_", 1)[0]


def count_survivors(paths: Iterable[Path]) -> Counter[str]:
    """Survivors per function across every shard's ``survivors.txt``."""
    counts: Counter[str] = Counter()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            name = function_of(line)
            if name is not None:
                counts[name] += 1
    return counts


def compare(
    baseline: dict[str, int], found: Counter[str]
) -> tuple[list[str], list[str]]:
    """Return ``(regressions, improvements)`` as printable lines."""
    worse = [
        f"{name}: {found[name]} survivors, baseline {baseline.get(name, 0)}"
        for name in sorted(found)
        if found[name] > baseline.get(name, 0)
    ]
    better = [
        f"{name}: {found[name]} survivors, baseline {count}"
        for name, count in sorted(baseline.items())
        if found[name] < count
    ]
    return worse, better


def _load(path: Path) -> dict[str, int]:
    """The baseline's per-function counts; empty when there is no file."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data["functions"].items()}


def _write(path: Path, found: Counter[str], score: str | None) -> None:
    """Write the counts, sorted, with the score that produced them."""
    payload = {
        "score": score,
        "survivors": sum(found.values()),
        "functions": dict(sorted(found.items())),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _report(
    worse: list[str],
    better: list[str],
    found: Counter[str],
    baseline: dict[str, int],
) -> None:
    """Print each worse and better function, then the totals."""
    for line in worse:
        print(f"  worse: {line}")
    for line in better:
        print(f"  better: {line}")
    print(
        f"mutation ratchet: {sum(found.values())} survivors in "
        f"{len(found)} functions (baseline {sum(baseline.values())}); "
        f"{len(worse)} worse, {len(better)} better"
    )


def main(argv: list[str] | None = None) -> int:
    """Print the comparison; exit 1 on any regression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument(
        "--survivors", type=Path, action="append", required=True
    )
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--score", help="recorded with --update")
    args = parser.parse_args(argv)
    missing = [p for p in args.survivors if not p.exists()]
    if missing:
        print(f"no survivor list at {missing[0]}", file=sys.stderr)
        return 1
    first = args.update and not args.baseline.exists()
    baseline = _load(args.baseline)
    found = count_survivors(args.survivors)
    worse, better = ([], []) if first else compare(baseline, found)
    _report(worse, better, found, baseline)
    if worse:
        if args.update:
            print("refusing to record a regression", file=sys.stderr)
        return 1
    if args.update:
        _write(args.baseline, found, args.score)
        print(f"baseline written to {args.baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
