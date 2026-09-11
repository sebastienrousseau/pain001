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

"""Print the column-to-element tables of ``docs/input-columns.md``.

The tables are derived from the templates by the records twin, so the
page cannot drift from what the pipeline renders. Paste the output into
the two edition sections after a template change.

Usage:
    poetry run python scripts/generate_input_columns.py [edition ...]
"""

from __future__ import annotations

import sys

from pain001.twins.records import column_paths


def table(version: str) -> str:
    """The Markdown table of one edition's columns."""
    rows = ["| Column | Element(s) |", "| :--- | :--- |"]
    for column, paths in column_paths(version).items():
        if column == "forwarding_agent_BIC":
            continue
        cells = "; ".join(f"`{p.split('/', 1)[1]}`" for p in paths)
        rows.append(f"| `{column}` | {cells or 'computed or not rendered'} |")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    """Print the tables for the editions given (default .03 and .09)."""
    editions = (argv if argv is not None else sys.argv[1:]) or [
        "pain.001.001.03",
        "pain.001.001.09",
    ]
    for version in editions:
        print(f"## {version}\n")
        print(table(version))
        print()
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
