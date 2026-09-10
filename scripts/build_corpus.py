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

"""Build the shipped corpus from the scenarios (ADR-0003, 3 and 6).

Every scenario under ``scenarios/`` renders to
``pain001/corpus/data/market/<country>/<family>/<id>.<version>.xml``
with a ``.provenance.yaml`` sidecar beside it carrying the scenario's
sources, confidence and evidence, the builder's fit report and the
file's SHA-256. Output is deterministic, so a rebuild on a clean tree
changes nothing and ``--check`` proves it.

The wheel budget from the plan, 400 KB compressed for everything under
``pain001/corpus/data``, is enforced here: the build fails when the
gzip'd size of the data tree exceeds it.

Usage:
    poetry run python scripts/build_corpus.py [--check] [--scenarios DIR]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from pain001.corpus.builder import BuildResult, build
from pain001.corpus.registry import SCENARIOS_DIR, Scenario, load_scenarios

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "pain001" / "corpus" / "data"
MARKET_ROOT = DATA_ROOT / "market"
#: Compressed-size budget for everything under pain001/corpus/data.
BUDGET_BYTES = 400_000


def target_for(
    scenario: Scenario, version: str, market_root: Path = MARKET_ROOT
) -> Path:
    """Where a scenario's rendering of ``version`` lives."""
    return (
        market_root
        / scenario.country.lower()
        / scenario.family
        / f"{scenario.id}.{version}.xml"
    )


def provenance_for(scenario: Scenario, result: BuildResult) -> str:
    """The sidecar text: scenario provenance plus how the file was built."""
    report = result.report
    record = {
        "scenario": scenario.id,
        "family": scenario.family,
        "country": scenario.country,
        "message_type": result.version,
        "description": scenario.data.get("description"),
        "sha256": hashlib.sha256(result.xml.encode("utf-8")).hexdigest(),
        "build": {
            "renamed": [f"{path} -> {name}" for path, name in report.renamed],
            "wrapped": list(report.wrapped),
            "unwrapped": list(report.unwrapped),
            "dropped": list(report.dropped),
            "truncated": list(report.truncated),
        },
        "provenance": scenario.data.get(
            "provenance", {"confidence": "assumed"}
        ),
        "constraints": scenario.data.get("constraints", []),
    }
    return yaml.safe_dump(record, sort_keys=False, allow_unicode=True)


def compressed_size(root: Path) -> int:
    """Sum of per-file gzip sizes under ``root``, the budget's measure."""
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_file():
            total += len(gzip.compress(path.read_bytes(), compresslevel=9))
    return total


def main(argv: list[str] | None = None) -> int:
    """Build (or with ``--check`` verify) the corpus.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when built or up to date within budget; 1 on a stale file,
        a build failure or a budget breach.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS_DIR)
    parser.add_argument(
        "--market-root", type=Path, default=MARKET_ROOT, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--data-root", type=Path, default=DATA_ROOT, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--budget", type=int, default=BUDGET_BYTES, help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.scenarios)
    if not scenarios:
        print(f"no scenarios under {args.scenarios}")
        return 1
    stale = 0
    expected: set[Path] = set()
    for scenario in scenarios:
        for version in scenario.versions:
            result = build(scenario, version)
            target = target_for(scenario, version, args.market_root)
            sidecar = target.with_suffix(".provenance.yaml")
            expected.update({target, sidecar})
            wanted = {
                target: result.xml,
                sidecar: provenance_for(scenario, result),
            }
            for path, text in wanted.items():
                current = (
                    path.read_text(encoding="utf-8") if path.exists() else None
                )
                if current == text:
                    continue
                stale += 1
                if args.check:
                    print(f"STALE       {_rel(path)}")
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                    print(f"wrote       {_rel(path)} ({len(text)} bytes)")
    for path in (
        sorted(args.market_root.rglob("*"))
        if args.market_root.exists()
        else []
    ):
        if path.is_file() and path not in expected:
            stale += 1
            if args.check:
                print(f"ORPHAN      {_rel(path)}")
            else:
                path.unlink()
                print(f"removed     {_rel(path)}")
    if args.check and stale:
        print(
            f"{stale} stale or orphaned file(s); run scripts/build_corpus.py"
        )
        return 1
    size = compressed_size(args.data_root) if args.data_root.exists() else 0
    print(
        f"{len(scenarios)} scenario(s), {len(expected) // 2} file(s); "
        f"data tree {size:,} bytes compressed of {args.budget:,} budget"
    )
    if size > args.budget:
        print("corpus data exceeds the compressed-size budget")
        return 1
    if not stale:
        print("up to date")
    return 0


def _rel(path: Path) -> str:
    """``path`` relative to the repository when inside it."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
