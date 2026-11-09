#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Audit the complete published pain001 family, including non-PyPI members."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ecosystem_audit import audit


def main(argv: list[str] | None = None) -> int:
    """Print/save the full report and fail when any publication is incomplete."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="audit this explicit stable version instead of latest",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable evidence"
    )
    parser.add_argument(
        "--output", type=Path, help="also write the JSON report to this file"
    )
    args = parser.parse_args(argv)
    report = audit(version=args.version or None)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    if args.json:
        print(payload, end="")
    else:
        state = "COMPLETE" if report["complete"] else "INCOMPLETE"
        print(
            f"pain001 {report['version']}: {state} ({len(report['members'])} repositories)"
        )
        for problem in report["problems"]:
            print("  - " + problem)
    return 0 if report["complete"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
