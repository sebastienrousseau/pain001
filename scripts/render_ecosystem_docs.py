#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Render the roadmap's publication table from docs/ecosystem.json."""

import sys
from pathlib import Path

from ecosystem_audit.documentation import roadmap_table

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Regenerate the component table or reject stale committed output."""
    path = ROOT / "ROADMAP.md"
    source = path.read_text()
    rendered = roadmap_table(source)
    if "--check" in sys.argv:
        if source != rendered:
            raise SystemExit(
                "ROADMAP is stale: run scripts/render_ecosystem_docs.py"
            )
    else:
        path.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
