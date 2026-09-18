#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Fail when the mutation score falls below the floor.

Reads ``mutants/mutmut-cicd-stats.json`` (``mutmut export-cicd-stats``).
The score is killed over checked: mutants no test reached, skipped
mutants and timeouts are reported but do not count either way, so the
number answers one question only: of the mutants the tests saw, how
many did they catch?

Usage: mutation_gate.py --floor 80 [--stats mutants/mutmut-cicd-stats.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def score(stats: dict) -> tuple[float, int, int]:
    """Return (percent killed of checked, killed, checked)."""
    killed = int(stats.get("killed", 0))
    survived = int(stats.get("survived", 0))
    checked = killed + survived
    return (100.0 * killed / checked if checked else 0.0, killed, checked)


def main(argv: list[str] | None = None) -> int:
    """Print the score and exit 1 below the floor."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--floor", type=float, required=True, help="minimum percent"
    )
    parser.add_argument("--stats", default="mutants/mutmut-cicd-stats.json")
    args = parser.parse_args(argv)
    path = Path(args.stats)
    if not path.exists():
        print(
            f"no mutation stats at {path}; run mutmut first", file=sys.stderr
        )
        return 1
    stats = json.loads(path.read_text(encoding="utf-8"))
    pct, killed, checked = score(stats)
    print(
        f"mutation score {pct:.1f}% ({killed} of {checked} checked mutants killed; "
        f"{stats.get('no_tests', 0)} unreached, "
        f"{stats.get('timeout', 0)} timed out, floor {args.floor:g}%)"
    )
    return 0 if pct >= args.floor else 1


if __name__ == "__main__":
    raise SystemExit(main())
