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

"""The ``make corpus-coverage`` gate.

For every bundled message type, measure its coverage set,
``pain001/corpus/data/coverage/<type>/*.xml``, against the schema
inventory. A version with no set yet is reported against its bundled
example for information and does not fail the gate. A version with a
set that leaves a non-exempt path or choice branch unused fails it:
that is the ADR-0003 acceptance rule, 100 % with a named exemption
list read from ``exemptions.txt`` beside the set (one path or branch
id per line, ``#`` comments allowed).

Usage:
    poetry run python scripts/corpus_coverage.py [--strict] [--json OUT]
    poetry run python scripts/corpus_coverage.py --inventory DIR

``--strict`` also fails when a version has no coverage set at all,
which is the setting CI moves to once every set exists.
``--inventory DIR`` writes each schema's inventory as JSON instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pain001.corpus import CoverageReport, coverage, inventory_for
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_ROOT = REPO_ROOT / "pain001" / "corpus" / "data" / "coverage"


def read_exemptions(set_dir: Path) -> list[str]:
    """Read ``exemptions.txt`` in ``set_dir``; missing means none."""
    path = set_dir / "exemptions.txt"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def measure(
    message_type: str, coverage_root: Path
) -> tuple[CoverageReport, bool]:
    """Measure one version.

    Args:
        message_type: The bundled message type.
        coverage_root: Directory holding ``<type>/`` coverage sets.

    Returns:
        The report and whether it came from a real coverage set
        (``False`` means the bundled example stood in).
    """
    set_dir = coverage_root / message_type
    files = sorted(set_dir.glob("*.xml")) if set_dir.is_dir() else []
    if files:
        return coverage(
            inventory_for(message_type), files, read_exemptions(set_dir)
        ), True
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    example = meta.example_xml_path
    sources = [example] if example is not None and example.exists() else []
    return coverage(inventory_for(message_type), sources), False


def write_inventories(out_dir: Path) -> int:
    """Write every bundled schema's inventory as JSON into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for meta in DEFAULT_TEMPLATE_REGISTRY.list_templates():
        inventory = inventory_for(meta.message_type)
        target = out_dir / f"{meta.message_type}.json"
        target.write_text(inventory.to_json(), encoding="utf-8")
        print(
            f"{meta.message_type}: {len(inventory.elements)} entries, "
            f"{len(inventory.choices)} choices -> {target}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the gate.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when every measured set is complete, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", type=Path, metavar="OUT")
    parser.add_argument("--inventory", type=Path, metavar="DIR")
    parser.add_argument(
        "--coverage-root",
        type=Path,
        default=COVERAGE_ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.inventory is not None:
        return write_inventories(args.inventory)

    failures = 0
    reports = {}
    print(f"{'message type':<17}{'paths':>9}{'branches':>10}  status")
    for meta in DEFAULT_TEMPLATE_REGISTRY.list_templates():
        report, real = measure(meta.message_type, args.coverage_root)
        reports[meta.message_type] = report.to_dict()
        if real:
            status = "complete" if report.complete else "INCOMPLETE"
            failures += not report.complete
        else:
            status = "no set (bundled example shown)"
            failures += args.strict
        print(
            f"{meta.message_type:<17}{report.path_percent:>8.1f}%"
            f"{report.branch_percent:>9.1f}%  {status}"
        )
        if real and not report.complete:
            for path in report.missing_paths[:10]:
                print(f"    missing path   {path}")
            for branch in report.missing_branches[:10]:
                print(f"    missing branch {branch}")
    if args.json is not None:
        args.json.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    if failures:
        print(f"{failures} version(s) fail the coverage gate")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
