# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Render the canonical portfolio README from reviewed repository evidence."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render() -> str:
    """Substitute evidence without altering the canonical layout."""
    values = json.loads((ROOT / "docs/readme-values.json").read_text())
    template = (ROOT / "docs/readme-template.md").read_text()
    return re.sub(
        r"\{\{([A-Z_]+)\}\}", lambda match: values[match[1]], template
    )


def main() -> None:
    """Regenerate the README, or fail if committed output has drifted."""
    rendered = render()
    target = ROOT / "README.md"
    if "--check" in sys.argv:
        if target.read_text() != rendered:
            raise SystemExit("README is stale: run scripts/render_readme.py")
    else:
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
