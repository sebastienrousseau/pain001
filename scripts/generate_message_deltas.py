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

"""Write ``docs/message-deltas.md``: what each ISO edition changed.

The document is computed from the bundled XSDs through the schema
inventory, one step per consecutive pair (pain.001.001.03 to .04 and
so on to .13, then pain.008.001.02 to .08). For each step it lists the
element paths added and removed, the paths whose type, facets or
cardinality changed, and the choice branches added or removed. Paths
are shown relative to the message root (``CstmrCdtTrfInitn`` or
``CstmrDrctDbtInitn``).

Usage:
    poetry run python scripts/generate_message_deltas.py [--check]

``--check`` writes nothing and exits 1 if the document is stale.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pain001.corpus import ElementEntry, Inventory, inventory_for

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "docs" / "message-deltas.md"

STEPS: list[tuple[str, str]] = [
    (f"pain.001.001.{a:02d}", f"pain.001.001.{a + 1:02d}")
    for a in range(3, 13)
] + [("pain.008.001.02", "pain.008.001.08")]


@dataclass(frozen=True)
class Delta:
    """The difference between two inventories."""

    old: Inventory
    new: Inventory
    added: list[ElementEntry]
    removed: list[ElementEntry]
    changed: list[tuple[ElementEntry, ElementEntry]]
    branches_added: list[str]
    branches_removed: list[str]


def _relative(path: str) -> str:
    """Drop ``/Document/<root>/`` so paths read from the message body."""
    parts = path.split("/", 3)
    return parts[3] if len(parts) > 3 else path


def _signature(entry: ElementEntry) -> tuple:
    return (
        entry.kind,
        entry.type_name,
        entry.min_occurs,
        entry.max_occurs,
        entry.primitive,
        tuple(sorted((k, str(v)) for k, v in entry.facets.items())),
    )


def compute(old_type: str, new_type: str) -> Delta:
    """Diff two bundled schemas by relative path.

    Args:
        old_type: The earlier message type.
        new_type: The later message type.

    Returns:
        The :class:`Delta`.
    """
    old, new = inventory_for(old_type), inventory_for(new_type)
    old_by = {_relative(e.path): e for e in old.elements}
    new_by = {_relative(e.path): e for e in new.elements}
    added = [new_by[p] for p in new_by if p not in old_by]
    removed = [old_by[p] for p in old_by if p not in new_by]
    changed = [
        (old_by[p], new_by[p])
        for p in old_by
        if p in new_by and _signature(old_by[p]) != _signature(new_by[p])
    ]
    old_branches = {_relative(b) for c in old.choices for b in c.branch_ids()}
    new_branches = {_relative(b) for c in new.choices for b in c.branch_ids()}
    return Delta(
        old,
        new,
        added,
        removed,
        changed,
        sorted(new_branches - old_branches),
        sorted(old_branches - new_branches),
    )


def _describe(entry: ElementEntry) -> str:
    """One-line description of an entry's type and cardinality."""
    card = f"{entry.min_occurs}..{'n' if entry.max_occurs is None else entry.max_occurs}"
    kind = entry.type_name or entry.kind
    bits = [kind, card]
    if "enumeration" in entry.facets:
        bits.append("enum " + "/".join(entry.facets["enumeration"]))
    if "patterns" in entry.facets:
        bits.append("pattern `" + "`, `".join(entry.facets["patterns"]) + "`")
    for key in ("min_length", "max_length", "total_digits", "fraction_digits"):
        if key in entry.facets:
            bits.append(f"{key.replace('_', ' ')} {entry.facets[key]}")
    return ", ".join(bits)


def _collapse(
    entries: list[ElementEntry],
) -> list[tuple[ElementEntry, int]]:
    """Keep subtree roots only, with the count of descendants folded in.

    When a whole block is added or removed, its descendants are listed
    as one line under the block's root rather than one line each.
    """
    paths = {e.path for e in entries}
    roots: list[tuple[ElementEntry, int]] = []
    for entry in entries:
        if not _has_ancestor_in(entry.path, paths):
            below = sum(1 for p in paths if p.startswith(entry.path + "/"))
            roots.append((entry, below))
    return roots


def _has_ancestor_in(path: str, paths: set[str]) -> bool:
    """True when a proper ancestor of ``path`` is in ``paths``."""
    parent = path.rsplit("/", 1)[0]
    while "/" in parent:
        if parent in paths:
            return True
        parent = parent.rsplit("/", 1)[0]
    return False


def _collapse_changed(
    changed: list[tuple[ElementEntry, ElementEntry]],
) -> list[tuple[ElementEntry, ElementEntry]]:
    """Drop type-name-only changes that merely follow an ancestor's."""
    paths = {o.path for o, _ in changed}
    kept = []
    for old, new in changed:
        old_sig, new_sig = _signature(old), _signature(new)
        only_type = old_sig[1] != new_sig[1] and (
            old_sig[:1] + old_sig[2:] == new_sig[:1] + new_sig[2:]
        )
        if not (only_type and _has_ancestor_in(old.path, paths)):
            kept.append((old, new))
    return kept


def _top_blocks(entries: list[ElementEntry]) -> str:
    """Count entries by their first path segment, for the summary."""
    counts = Counter(_relative(e.path).split("/", 1)[0] for e in entries)
    return ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))


def render(deltas: list[Delta]) -> str:
    """Render the deltas as Markdown.

    Args:
        deltas: One per step, in order.

    Returns:
        The document text.
    """
    lines = [
        "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->",
        "<!-- Generated by scripts/generate_message_deltas.py; do not edit. -->",
        "",
        "# What each ISO 20022 edition changed",
        "",
        "Computed from the bundled XSDs through `pain001.corpus.inventory`, one",
        "step per consecutive edition. Paths are relative to the message body",
        "(`CstmrCdtTrfInitn` for pain.001, `CstmrDrctDbtInitn` for pain.008);",
        "`@name` is an attribute and `*` an `xs:any` slot. A *changed* path kept",
        "its name but changed type, facets or cardinality. Choice branches are",
        "written `holder -> first element`.",
        "",
        "## Summary",
        "",
        "| Step | Paths (old → new) | Added | Removed | Changed | Branches +/− |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for d in deltas:
        lines.append(
            f"| {d.old.message_type} → {d.new.message_type} "
            f"| {len(d.old.elements)} → {len(d.new.elements)} "
            f"| {len(d.added)} | {len(d.removed)} | {len(d.changed)} "
            f"| +{len(d.branches_added)} / −{len(d.branches_removed)} |"
        )
    for d in deltas:
        lines += ["", f"## {d.old.message_type} → {d.new.message_type}", ""]
        if not (
            d.added
            or d.removed
            or d.changed
            or d.branches_added
            or d.branches_removed
        ):
            lines.append("No structural change.")
            continue
        if d.added:
            lines += [
                f"### Added ({len(d.added)}: {_top_blocks(d.added)})",
                "",
            ]
            lines += [
                f"- `{_relative(e.path)}` — {_describe(e)}"
                + (f" (+{n} paths below)" if n else "")
                for e, n in _collapse(d.added)
            ]
            lines.append("")
        if d.removed:
            lines += [
                f"### Removed ({len(d.removed)}: {_top_blocks(d.removed)})",
                "",
            ]
            lines += [
                f"- `{_relative(e.path)}` — was {_describe(e)}"
                + (f" (+{n} paths below)" if n else "")
                for e, n in _collapse(d.removed)
            ]
            lines.append("")
        if d.changed:
            shown = _collapse_changed(d.changed)
            hidden = len(d.changed) - len(shown)
            note = (
                f", {hidden} type renames that follow a parent's omitted"
                if hidden
                else ""
            )
            lines += [f"### Changed ({len(d.changed)}{note})", ""]
            lines += [
                f"- `{_relative(o.path)}` — {_describe(o)} → {_describe(n)}"
                for o, n in shown
            ]
            lines.append("")
        if d.branches_added:
            lines += [
                f"### Choice branches added ({len(d.branches_added)})",
                "",
            ]
            lines += [f"- `{b}`" for b in d.branches_added]
            lines.append("")
        if d.branches_removed:
            lines += [
                f"### Choice branches removed ({len(d.branches_removed)})",
                "",
            ]
            lines += [f"- `{b}`" for b in d.branches_removed]
            lines.append("")
    # Sections end with a blank and the next begins with one; keep one.
    squeezed: list[str] = []
    for line in lines:
        if line == "" and squeezed and squeezed[-1] == "":
            continue
        squeezed.append(line)
    while squeezed and squeezed[-1] == "":
        squeezed.pop()
    return "\n".join(squeezed) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write (or with ``--check`` verify) the document.

    Args:
        argv: Command-line arguments; ``--check`` verifies only.

    Returns:
        0 when written or up to date, 1 when ``--check`` found it stale.
    """
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    text = render([compute(a, b) for a, b in STEPS])
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if current == text:
        print(f"up to date  {OUT.relative_to(REPO_ROOT)}")
        return 0
    if check:
        print(
            f"STALE       {OUT.relative_to(REPO_ROOT)}; run scripts/generate_message_deltas.py"
        )
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote       {OUT.relative_to(REPO_ROOT)} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
