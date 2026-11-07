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

"""Build the ISO 2018 face's tag-to-name table (ADR-0005).

The ISO 20022 Registration Authority's Message Definition Reports, Part 2,
state every message element with its XML tag, as ``GroupHeader
<GrpHdr>``. This script reads those reports (PDF, through ``pdftotext``
from poppler) from a directory outside the repository, keeps the tags
the bundled pain.001 schemas use, and writes
``pain001/faces/iso_names.json`` with the report files and the read
date. The reports themselves are never copied into the tree.

A tag no report names is listed under ``unresolved`` with the reason,
never guessed; the ISO 2018 face leaves those elements to its loss
report. ``--check`` needs no reports: it proves the shipped table
accounts for every tag of every bundled pain.001 schema.

Usage:
    python scripts/build_iso_name_table.py --mdr-dir DIR [--read-date YYYY-MM-DD]
    python scripts/build_iso_name_table.py --check
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "pain001" / "templates"
TABLE = ROOT / "pain001" / "faces" / "iso_names.json"
XS = "{http://www.w3.org/2001/XMLSchema}"
PAIR = re.compile(
    r"(?<![A-Za-z<])([A-Z][A-Za-z0-9]*)\s+<([A-Za-z][A-Za-z0-9]*)>"
)
# The message root is not projected: the face emits the message content.
ROOT_TAGS = frozenset({"Document", "CstmrCdtTrfInitn"})
# Words of the report's own layout that precede a tag but are not names.
NOT_NAMES = frozenset({"Or", "Message", "root"})
UNRESOLVED_REASONS = {
    "BIC": "pain.001.001.03 only; no Message Definition Report in the "
    "source set covers its 2009 release",
    "BICOrBEI": "pain.001.001.03 only; no Message Definition Report in the "
    "source set covers its 2009 release",
}
NEWER_THAN_SOURCE = (
    "introduced after the newest Message Definition Report in the source set"
)


def bundled_tags() -> dict[str, set[str]]:
    """Every element tag of each bundled pain.001 schema, by edition."""
    out: dict[str, set[str]] = {}
    for directory in sorted(TEMPLATES.glob("pain.001.001.*")):
        root = ET.parse(next(directory.glob("*.xsd"))).getroot()
        names = (el.get("name") for el in root.iter(f"{XS}element"))
        out[directory.name] = {name for name in names if name}
    return out


def read_pairs(text: str) -> list[tuple[str, str]]:
    """``(name, tag)`` pairs in a report's text."""
    return [(n, t) for n, t in PAIR.findall(text) if n not in NOT_NAMES]


def names_from_reports(texts: dict[str, str]) -> dict[str, str]:
    """One name per tag across the reports; a tag with two names fails."""
    seen: dict[str, Counter[str]] = defaultdict(Counter)
    for text in texts.values():
        for name, tag in read_pairs(text):
            seen[tag][name] += 1
    conflicts = {t: dict(c) for t, c in seen.items() if len(c) > 1}
    if conflicts:
        raise SystemExit(f"tags with more than one name: {conflicts}")
    return {tag: next(iter(c)) for tag, c in seen.items()}


def build_table(
    texts: dict[str, str], read_date: str, tags: dict[str, set[str]]
) -> dict[str, object]:
    """The table for the bundled tags, from the reports' texts."""
    known = names_from_reports(texts)
    wanted = set().union(*tags.values()) - ROOT_TAGS
    names = {t: known[t] for t in sorted(wanted) if t in known}
    unresolved = {
        t: UNRESOLVED_REASONS.get(t, NEWER_THAN_SOURCE)
        for t in sorted(wanted - set(names))
    }
    return {
        "source": "ISO 20022 Message Definition Reports, Part 2, Payments Initiation",
        "reports": sorted(texts),
        "read_date": read_date,
        "names": names,
        "unresolved": unresolved,
    }


def pdf_texts(directory: Path) -> dict[str, str]:
    """``pdftotext -layout`` of every PDF in ``directory``, by file name."""
    tool = shutil.which("pdftotext")
    if tool is None:
        raise SystemExit("pdftotext (poppler) is required to read the reports")
    out = {}
    for pdf in sorted(directory.glob("*.pdf")):
        run = subprocess.run(
            [tool, "-layout", str(pdf), "-"],
            capture_output=True,
            check=True,
        )
        out[pdf.name] = run.stdout.decode("utf-8", errors="replace")
    if not out:
        raise SystemExit(f"no PDF report in {directory}")
    return out


def check(table: dict[str, object], tags: dict[str, set[str]]) -> list[str]:
    """Problems with a table against the bundled schemas; empty when sound."""
    names = table.get("names")
    unresolved = table.get("unresolved")
    if not isinstance(names, dict) or not isinstance(unresolved, dict):
        return ["the table needs 'names' and 'unresolved' objects"]
    problems = [
        f"{version}: {tag} is neither named nor listed as unresolved"
        for version, version_tags in sorted(tags.items())
        for tag in sorted(version_tags - ROOT_TAGS)
        if tag not in names and tag not in unresolved
    ]
    problems += [
        f"{t} is both named and unresolved"
        for t in set(names) & set(unresolved)
    ]
    for key in ("source", "reports", "read_date"):
        if not table.get(key):
            problems.append(f"missing provenance field {key!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Build or check the table."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--mdr-dir", type=Path, help="directory of MDR Part 2 PDFs"
    )
    parser.add_argument("--read-date", default=dt.date.today().isoformat())
    parser.add_argument(
        "--check", action="store_true", help="check the shipped table"
    )
    args = parser.parse_args(argv)
    tags = bundled_tags()
    if args.check:
        problems = check(json.loads(TABLE.read_text(encoding="utf-8")), tags)
        for problem in problems:
            print(problem, file=sys.stderr)
        if not problems:
            print(
                f"{TABLE.relative_to(ROOT)} accounts for every bundled pain.001 tag"
            )
        return 1 if problems else 0
    if args.mdr_dir is None:
        parser.error("--mdr-dir is required unless --check is given")
    table = build_table(pdf_texts(args.mdr_dir), args.read_date, tags)
    TABLE.write_text(
        json.dumps(table, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {TABLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
