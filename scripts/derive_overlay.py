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

"""Author tool: what a usage-guideline schema changes against the ISO base.

A bank or scheme publishes its usage guideline on MyStandards under
restricted terms; the export (PDF, XSD) stays outside this repository
in the maintainer's own storage. This script reads such an XSD from
wherever it is, inventories it, diffs it against the bundled ISO edition
and prints the differences: removed elements, elements made mandatory,
repeats capped, code lists narrowed, lengths shortened, patterns
changed. It writes nothing. The author then decides which few of those
constraints a scenario variant needs, and commits them as a short
overlay with a prose citation; the full list is not committed.

Usage:
    poetry run python scripts/derive_overlay.py GUIDELINE.xsd \\
        --base pain.001.001.03 [--as-rules]

``--as-rules`` prints the differences in overlay rule syntax as a
starting point for curation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pain001.corpus.inventory import (
    ElementEntry,
    build_inventory,
    inventory_for,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _relative(path: str) -> str:
    """The path from the message root, ``PmtInf/...``."""
    parts = path.split("/", 3)
    return parts[3] if len(parts) > 3 else path


def diff(guideline: Path, base_version: str) -> dict[str, list]:
    """Inventory the guideline and compare it with the base edition.

    Args:
        guideline: The usage-guideline XSD (outside the repository).
        base_version: The ISO edition it restricts.

    Returns:
        Lists keyed ``removed``, ``mandatory``, ``capped``, ``enum``,
        ``length``, ``pattern``; each item starts with the relative path.
    """
    ug = build_inventory(guideline, "guideline")
    base = inventory_for(base_version)
    b = {e.path: e for e in base.elements}
    u = {e.path: e for e in ug.elements}
    removed_all = [p for p in b if p not in u]
    removed = [
        p
        for p in removed_all
        if not any(p.startswith(q + "/") for q in removed_all if q != p)
    ]

    def entry(p: str) -> ElementEntry:
        return u[p]

    return {
        "removed": [(_relative(p),) for p in removed],
        "mandatory": [
            (_relative(p), b[p].min_occurs, entry(p).min_occurs)
            for p in u
            if p in b and entry(p).min_occurs > b[p].min_occurs
        ],
        "capped": [
            (_relative(p), b[p].max_occurs, entry(p).max_occurs)
            for p in u
            if p in b
            and (entry(p).max_occurs or 10**6) < (b[p].max_occurs or 10**6)
        ],
        "enum": [
            (_relative(p), entry(p).facets["enumeration"])
            for p in u
            if p in b
            and "enumeration" in entry(p).facets
            and entry(p).facets["enumeration"]
            != b[p].facets.get("enumeration")
        ],
        "length": [
            (
                _relative(p),
                b[p].facets.get("max_length"),
                entry(p).facets.get("max_length"),
            )
            for p in u
            if p in b
            and entry(p).facets.get("max_length")
            and entry(p).facets.get("max_length")
            != b[p].facets.get("max_length")
        ],
        "pattern": [
            (_relative(p), entry(p).facets.get("patterns"))
            for p in u
            if p in b
            and entry(p).facets.get("patterns") != b[p].facets.get("patterns")
        ],
    }


def as_rules(changes: dict[str, list]) -> list[str]:
    """Overlay rule lines for the changes, one YAML list item per line."""
    lines: list[str] = []
    for (path,) in changes["removed"]:
        lines.append(f"- {{locator: {path}, assertion: forbidden}}")
    for path, _, _ in changes["mandatory"]:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        cond = f"if:{parent}:" if parent else ""
        lines.append(f"- {{locator: {path}, assertion: {cond}required}}")
    for path, values in changes["enum"]:
        lines.append(
            f"- {{locator: {path}, assertion: 'one_of:[{', '.join(values)}]'}}"
        )
    for path, _, new in changes["length"]:
        lines.append(f"- {{locator: {path}, assertion: max_length:{new}}}")
    for path, patterns in changes["pattern"]:
        for pattern in patterns or []:
            lines.append(
                f"- {{locator: {path}, assertion: 'matches:{pattern}'}}"
            )
    return lines


def main(argv: list[str] | None = None) -> int:
    """Print the diff.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0, or 1 when the guideline path is inside the repository.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("guideline", type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--as-rules", action="store_true")
    args = parser.parse_args(argv)
    guideline = args.guideline.resolve()
    if guideline.is_relative_to(REPO_ROOT):
        print(
            "refusing: a guideline export must not live inside the repository"
        )
        return 1
    changes = diff(guideline, args.base)
    if args.as_rules:
        print("\n".join(as_rules(changes)))
        return 0
    for kind, items in changes.items():
        print(f"{kind} ({len(items)})")
        for item in items:
            print("   ", *item)
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
