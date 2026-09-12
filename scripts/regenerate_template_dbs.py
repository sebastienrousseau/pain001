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

"""Rebuild every bundle's ``template.db`` from its ``template.csv``.

The SQLite mirror has one table, ``pain001``, with every CSV column as
TEXT and the rows in CSV order. It exists so the SQLite loader has a
sample to read; the CSV is the source of truth. Run this after editing
any ``template.csv``; covers every registered message type, pain.008
included.

Usage:
    poetry run python scripts/regenerate_template_dbs.py [--check]

``--check`` rebuilds nothing and exits 1 if any database differs from
its CSV.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLE = "pain001"


def _rows_and_columns(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    """Read ``csv_path`` into column names and row values."""
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = [[row[col] for col in columns] for row in reader]
    return columns, rows


def _db_contents(db_path: Path) -> tuple[list[str], list[list[str]]]:
    """Read the ``pain001`` table of ``db_path`` in row order."""
    if not db_path.exists():
        return [], []
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(f'SELECT * FROM "{TABLE}"')
        columns = [d[0] for d in cur.description]
        rows = [list(map(str, r)) for r in cur.fetchall()]
    except sqlite3.DatabaseError:
        return [], []
    finally:
        conn.close()
    return columns, rows


def rebuild(db_path: Path, columns: list[str], rows: list[list[str]]) -> None:
    """Write ``columns``/``rows`` as a fresh ``pain001`` table."""
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        col_def = ", ".join(f'"{col}" TEXT' for col in columns)
        conn.execute(f'CREATE TABLE "{TABLE}" ({col_def})')
        placeholders = ", ".join("?" for _ in columns)
        conn.executemany(
            f'INSERT INTO "{TABLE}" VALUES ({placeholders})', rows
        )
        conn.commit()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    """Rebuild (or with ``--check`` verify) every bundle's SQLite mirror.

    Args:
        argv: Command-line arguments; ``--check`` verifies only.

    Returns:
        Process exit code: 0 when every database matches its CSV or was
        rebuilt, 1 when ``--check`` found a stale one.
    """
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    stale = 0
    for meta in DEFAULT_TEMPLATE_REGISTRY.list_templates():
        base = meta.template_path.parent
        csv_path = base / "template.csv"
        db_path = base / "template.db"
        columns, rows = _rows_and_columns(csv_path)
        if _db_contents(db_path) == (columns, rows):
            print(f"up to date  {db_path.relative_to(REPO_ROOT)}")
            continue
        stale += 1
        if check:
            print(f"STALE       {db_path.relative_to(REPO_ROOT)}")
        else:
            rebuild(db_path, columns, rows)
            print(
                f"rebuilt     {db_path.relative_to(REPO_ROOT)} ({len(rows)} rows)"
            )
    if check and stale:
        print(
            f"{stale} stale database(s); run scripts/regenerate_template_dbs.py"
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
