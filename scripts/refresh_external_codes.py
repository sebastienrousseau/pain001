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


"""Swap in a newer edition of the ISO external code sets.

Download the JSON edition from iso20022.org (External Code Sets, no
login), then:

    poetry run python scripts/refresh_external_codes.py NEW.json

The script diffs the vendored edition against the new one, scans the
bundled data (templates, corpus data) for every code the new edition
withdrew, and refuses to switch if any withdrawn code is still in use.
Otherwise it replaces the vendored file, keeping the new file's stem as
the edition name, and prints what changed.

``--dry-run`` reports without replacing.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from pain001.corpus.rules.external_codes import (
    DATA_DIR,
    edition_file,
    load_definitions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCAN = (
    REPO_ROOT / "pain001" / "templates",
    REPO_ROOT / "pain001" / "corpus" / "data",
)


def diff_editions(
    old: dict[str, dict], new: dict[str, dict]
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str], list[str]]:
    """Compare two editions' definitions.

    Args:
        old: The vendored edition's definitions.
        new: The candidate edition's definitions.

    Returns:
        ``(added, withdrawn, new_sets, dropped_sets)``: codes added and
        withdrawn per set, and set names that appeared or vanished.
    """
    added: dict[str, list[str]] = {}
    withdrawn: dict[str, list[str]] = {}
    for name in sorted(set(old) | set(new)):
        before = set(old.get(name, {}).get("enum") or [])
        after = set(new.get(name, {}).get("enum") or [])
        if after - before:
            added[name] = sorted(after - before)
        if before - after and name in new:
            withdrawn[name] = sorted(before - after)
    new_sets = sorted(set(new) - set(old))
    dropped = sorted(set(old) - set(new))
    for name in dropped:
        if old[name].get("enum"):
            withdrawn[name] = sorted(old[name]["enum"])
    return added, withdrawn, new_sets, dropped


def usages(code: str, roots: tuple[Path, ...]) -> list[Path]:
    """Files under ``roots`` that carry ``code`` as an XML value or CSV cell.

    Args:
        code: The code to look for.
        roots: Directories to scan for ``*.xml`` and ``*.csv``.

    Returns:
        The files using it, sorted.
    """
    pattern = re.compile(
        rf"(>{re.escape(code)}<|(^|,){re.escape(code)}(,|$))", re.M
    )
    hits: list[Path] = []
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".xml", ".csv") or not path.is_file():
                continue
            if pattern.search(
                path.read_text(encoding="utf-8", errors="replace")
            ):
                hits.append(path)
    return hits


def main(argv: list[str] | None = None) -> int:
    """Run the refresh.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when the edition was replaced (or ``--dry-run`` found no
        blocker), 1 when a withdrawn code is still in use.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("new_edition", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--data-dir", type=Path, default=DATA_DIR, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--scan",
        type=Path,
        action="append",
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    roots = tuple(args.scan) if args.scan else DEFAULT_SCAN

    current = edition_file(args.data_dir)
    old = load_definitions(current)
    new = load_definitions(args.new_edition)
    added, withdrawn, new_sets, dropped = diff_editions(old, new)
    print(f"{current.stem} -> {args.new_edition.stem}")
    print(
        f"  sets: {len(old)} -> {len(new)} (+{len(new_sets)} / -{len(dropped)}); "
        f"codes added in {len(added)} set(s), withdrawn in {len(withdrawn)} set(s)"
    )
    for name, values in added.items():
        print(f"  + {name}: {', '.join(values)}")
    blockers = 0
    for name, values in withdrawn.items():
        for code in values:
            used = usages(code, roots)
            mark = "BLOCKED" if used else "-"
            print(
                f"  {mark} {name}: {code}"
                + (
                    f" used in {', '.join(str(u.relative_to(REPO_ROOT)) if u.is_relative_to(REPO_ROOT) else str(u) for u in used)}"
                    if used
                    else ""
                )
            )
            blockers += bool(used)
    if blockers:
        print(
            f"{blockers} withdrawn code(s) still in use; edition not replaced"
        )
        return 1
    if args.dry_run:
        print("dry run; edition not replaced")
        return 0
    target = args.data_dir / f"{args.new_edition.stem}.json"
    shutil.copyfile(args.new_edition, target)
    if target != current:
        current.unlink()
    print(f"vendored {target.name}")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
