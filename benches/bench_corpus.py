#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What the example corpus costs to build and to judge.

The corpus engine does four kinds of work, and each has a different
cost curve worth knowing before it lands in a pipeline:

* **inventory**: walking an edition's XSD into paths and choice
  branches. Once per edition, cached afterwards; the cost is the schema's
  size (pain.001.001.13 declares 1,700 paths).
* **build**: composing one scenario into one edition and validating it
  against the XSD. This is what a private bank-variant build repeats per
  scenario, so it is measured per file.
* **ladder**: the four rungs on a built file (XSD, ISO MDR rules, rail
  profile, overlay). The MDR and rail rungs are pure Python; the XSD
  rung dominates.
* **coverage set**: generating an edition's schema coverage files, a
  search that emits a file, measures, and repeats until every path and
  branch is hit. This is the expensive one and runs only when the corpus
  is rebuilt.

Run::

    python benches/bench_corpus.py
    python benches/bench_corpus.py --json
    python benches/bench_corpus.py --quick     # what CI runs

Nothing here asserts a threshold: wall-clock is not comparable between
machines, and a flaky performance gate teaches people to ignore red. CI
runs ``--quick`` so a benchmark that has stopped compiling against the
current API fails the build instead of rotting into a file that reads
as verified and is not.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pain001.corpus import (  # noqa: E402
    build,
    build_coverage_set,
    build_inventory,
    load_scenarios,
)
from pain001.corpus.rules.ladder import run_ladder  # noqa: E402
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY  # noqa: E402


def _best(call, repeats: int) -> float:
    """The fastest of ``repeats`` runs, in seconds."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        samples.append(time.perf_counter() - start)
    return min(samples)


def run(quick: bool) -> dict:
    """Measure the four kinds of work.

    Args:
        quick: Fewer scenarios, one edition, one repeat; what CI runs.

    Returns:
        The measurements, JSON-ready.
    """
    repeats = 1 if quick else 3
    editions = (
        ["pain.001.001.03"]
        if quick
        else ["pain.001.001.03", "pain.001.001.13"]
    )
    results: dict = {
        "inventory": [],
        "build": [],
        "ladder": [],
        "coverage_set": [],
    }

    for edition in editions:
        xsd = DEFAULT_TEMPLATE_REGISTRY.get_template(edition).xsd_path
        inventory = build_inventory(xsd, edition)
        seconds = _best(partial(build_inventory, xsd, edition), repeats)
        results["inventory"].append(
            {
                "edition": edition,
                "paths": len(inventory.paths()),
                "ms": seconds * 1e3,
            }
        )

    scenarios = load_scenarios()
    scenarios = scenarios[:3] if quick else scenarios
    for scenario in scenarios:
        for edition in scenario.versions:
            if quick and edition not in ("pain.001.001.03", "pain.008.001.02"):
                continue
            result = build(scenario, edition)
            seconds = _best(partial(build, scenario, edition), repeats)
            results["build"].append(
                {
                    "scenario": scenario.id,
                    "edition": edition,
                    "bytes": len(result.xml),
                    "ms": seconds * 1e3,
                }
            )
            seconds = _best(
                partial(run_ladder, scenario, edition, result.xml), repeats
            )
            results["ladder"].append(
                {
                    "scenario": scenario.id,
                    "edition": edition,
                    "ms": seconds * 1e3,
                }
            )

    for edition in editions:
        start = time.perf_counter()
        generated = build_coverage_set(edition)
        results["coverage_set"].append(
            {
                "edition": edition,
                "files": len(generated.files),
                "complete": generated.report.complete,
                "ms": (time.perf_counter() - start) * 1e3,
            }
        )
    return results


def render(results: dict) -> None:
    """Print the measurements as tables."""
    print("inventory (per edition)")
    for row in results["inventory"]:
        print(
            f"  {row['edition']:<18} {row['paths']:>6} paths  {row['ms']:>8.1f} ms"
        )
    print("build + ladder (per file)")
    for b, lad in zip(results["build"], results["ladder"], strict=True):
        print(
            f"  {b['scenario']:<30} {b['edition']:<16} {b['bytes']:>6} B  "
            f"build {b['ms']:>7.1f} ms  ladder {lad['ms']:>7.1f} ms"
        )
    print("coverage set (per edition)")
    for row in results["coverage_set"]:
        state = "complete" if row["complete"] else "INCOMPLETE"
        print(
            f"  {row['edition']:<18} {row['files']:>3} files  {row['ms']:>8.0f} ms  {state}"
        )


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="fewer scenarios and one edition, as CI runs",
    )
    args = parser.parse_args()
    results = run(quick=args.quick)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        render(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
