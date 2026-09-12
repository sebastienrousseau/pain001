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

"""Build the shipped corpus (ADR-0003, decisions 2, 3 and 6).

Two trees come out, both deterministic, so a rebuild on a clean tree
changes nothing and ``--check`` proves it:

* the market corpus: every scenario under ``scenarios/`` renders to
  ``pain001/corpus/data/market/<country>/<family>/<id>.<version>.xml``
  with a ``.provenance.yaml`` sidecar beside it carrying the scenario's
  sources, confidence and evidence, the builder's fit report and the
  file's SHA-256;
* the coverage corpus: every bundled edition gets
  ``pain001/corpus/data/coverage/<version>/NN-<recipe>-<focus>.xml`` generated from
  its schema inventory until every element path and choice branch is
  hit, plus ``coverage.json`` with the report ``make corpus-coverage``
  re-checks.

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
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from pain001.constants import valid_xml_types
from pain001.corpus.builder import BuildResult, build
from pain001.corpus.coverage_sets import CoverageFileInfo, build_coverage_set
from pain001.corpus.inventory import CoverageReport
from pain001.corpus.registry import SCENARIOS_DIR, Scenario, load_scenarios
from pain001.corpus.rules.ladder import ladder_passes, run_ladder
from pain001.corpus.rules.overlays import Overlay, load_overlays

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "pain001" / "corpus" / "data"
MARKET_ROOT = DATA_ROOT / "market"
COVERAGE_ROOT = DATA_ROOT / "coverage"
#: Compressed-size budget for everything under pain001/corpus/data.
BUDGET_BYTES = 400_000


def target_for(
    scenario: Scenario,
    version: str,
    market_root: Path = MARKET_ROOT,
    variant: str | None = None,
) -> Path:
    """Where a scenario's rendering of ``version`` lives.

    A bank variant built with an overlay's patch is named
    ``<scenario>__<overlay>.<version>.xml`` beside the generic file.
    """
    stem = scenario.id if variant is None else f"{scenario.id}__{variant}"
    return (
        market_root
        / scenario.country.lower()
        / scenario.family
        / f"{stem}.{version}.xml"
    )


def variants_for(
    scenario: Scenario, pool: list[Overlay], version: str | None = None
) -> list[Overlay]:
    """The overlays with a patch that target the scenario and edition."""
    wanted = scenario.overlays
    chosen = []
    for overlay in pool:
        if not overlay.has_patch:
            continue
        if (
            version is not None
            and overlay.versions
            and version not in overlay.versions
        ):
            continue
        if wanted is None and not overlay.applies(
            scenario.id, scenario.family
        ):
            continue
        if wanted is not None and overlay.overlay_id not in wanted:
            continue
        chosen.append(overlay)
    return chosen


def provenance_for(
    scenario: Scenario,
    result: BuildResult,
    variant: Overlay | None = None,
    pool: list[Overlay] | None = None,
) -> str:
    """The sidecar text: provenance, how the file was built, and the ladder.

    Args:
        scenario: The scenario.
        result: The build result for one edition.
        variant: The overlay whose patch built this file, if any.
        pool: The overlay pool; defaults to ``scenarios/overlays``.

    Returns:
        YAML text.

    Raises:
        SystemExit: If the file fails a rung of the validation ladder;
            a file that cannot pass is not shipped.
    """
    report = result.report
    ladder = run_ladder(
        scenario,
        result.version,
        result.xml,
        pool,
        variant.overlay_id if variant else None,
    )
    if not ladder_passes(ladder):
        raise SystemExit(
            f"{scenario.id} in {result.version} fails the validation ladder: "
            f"{ladder}"
        )
    record = {
        "scenario": scenario.id,
        "family": scenario.family,
        "country": scenario.country,
        "message_type": result.version,
        "variant": (
            {
                "overlay": variant.overlay_id,
                "title": variant.title,
                "source": variant.source,
                "patch": variant.patch_for(scenario.id),
            }
            if variant
            else None
        ),
        "description": scenario.data.get("description"),
        "sha256": hashlib.sha256(result.xml.encode("utf-8")).hexdigest(),
        "build": {
            "renamed": [f"{path} -> {name}" for path, name in report.renamed],
            "wrapped": list(report.wrapped),
            "unwrapped": list(report.unwrapped),
            "dropped": list(report.dropped),
            "truncated": list(report.truncated),
        },
        "validation": ladder,
        "provenance": scenario.data.get(
            "provenance", {"confidence": "assumed"}
        ),
        "constraints": scenario.data.get("constraints", []),
    }
    return yaml.safe_dump(record, sort_keys=False, allow_unicode=True)


def slim_report(
    report: CoverageReport, manifest: Sequence[CoverageFileInfo]
) -> dict[str, Any]:
    """The coverage verdict without the hit lists, which the gate recomputes.

    Args:
        report: The set's coverage report.
        manifest: What each file of the set is for, in order.

    Returns:
        A JSON-ready dict: sources, what each file is for, counts,
        percentages, completeness, and the missing, exempt and unknown
        lists.
    """
    return {
        "message_type": report.message_type,
        "sources": [info.name for info in manifest],
        "files": [
            {
                "name": info.name,
                "recipe": info.recipe,
                "description": info.description,
                "focus": list(info.focus),
                "adds_paths": info.adds_paths,
                "adds_branches": info.adds_branches,
            }
            for info in manifest
        ],
        "paths": {
            "declared": len(report.hit_paths) + len(report.missing_paths),
            "hit": len(report.hit_paths),
            "percent": round(report.path_percent, 2),
        },
        "branches": {
            "declared": len(report.hit_branches)
            + len(report.missing_branches),
            "hit": len(report.hit_branches),
            "percent": round(report.branch_percent, 2),
        },
        "complete": report.complete,
        "missing_paths": list(report.missing_paths),
        "missing_branches": list(report.missing_branches),
        "exempt": list(report.exempt),
        "unknown": list(report.unknown),
    }


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
        "--coverage-root",
        type=Path,
        default=COVERAGE_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--skip-coverage", action="store_true", help=argparse.SUPPRESS
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
    pool = load_overlays()
    for scenario in scenarios:
        for version in scenario.versions:
            renderings = [(None, build(scenario, version))]
            for overlay in variants_for(scenario, pool, version):
                renderings.append(
                    (
                        overlay,
                        build(
                            scenario, version, overlay.patch_for(scenario.id)
                        ),
                    )
                )
            wanted: dict[Path, str] = {}
            for overlay, result in renderings:
                variant = overlay.overlay_id if overlay else None
                target = target_for(
                    scenario, version, args.market_root, variant
                )
                sidecar = target.with_suffix(".provenance.yaml")
                wanted[target] = result.xml
                wanted[sidecar] = provenance_for(
                    scenario, result, overlay, pool
                )
            expected.update(wanted)
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
    if not args.skip_coverage:
        for version in valid_xml_types:
            coverage_set = build_coverage_set(version)
            set_dir = args.coverage_root / version
            wanted = {
                set_dir / info.name: text
                for info, text in zip(
                    coverage_set.manifest, coverage_set.files, strict=True
                )
            }
            report = slim_report(coverage_set.report, coverage_set.manifest)
            wanted[set_dir / "coverage.json"] = (
                json.dumps(report, indent=2) + "\n"
            )
            expected.update(wanted)
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
    roots = [args.market_root]
    if not args.skip_coverage:
        roots.append(args.coverage_root)
    present = sorted(
        p for root in roots if root.exists() for p in root.rglob("*")
    )
    for path in present:
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
        f"{len(scenarios)} scenario(s), {len(expected)} file(s); "
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
