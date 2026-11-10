# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Write conformance/openapi.json from the REST app (``--check`` to verify).

The server's own version is replaced by the kit version, so the snapshot
only changes when the API does, not on every release.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "conformance"


def render() -> str:
    """The normalised OpenAPI document as text."""
    from pain001.api.app import app  # noqa: PLC0415

    # FastAPI caches the document it returns; work on a copy so the
    # running app keeps reporting its real version.
    spec: dict[str, Any] = copy.deepcopy(app.openapi())
    kit_version = json.loads((KIT / "cases.json").read_text(encoding="utf-8"))[
        "kit_version"
    ]
    spec["info"]["version"] = f"conformance-kit-{kit_version}"
    return json.dumps(spec, indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    """Write the snapshot, or with ``--check`` report drift (exit 1)."""
    target = KIT / "openapi.json"
    text = render()
    if "--check" in argv:
        if target.read_text(encoding="utf-8") != text:
            print(
                "conformance/openapi.json is stale: run "
                "scripts/build_conformance_openapi.py",
                file=sys.stderr,
            )
            return 1
        return 0
    target.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
