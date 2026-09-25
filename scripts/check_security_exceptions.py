# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Fail closed when an accepted release risk needs review or has expired."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    """Validate the registry and enforce both review and expiry deadlines."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path, default=ROOT / "docs/security-exceptions.json"
    )
    parser.add_argument(
        "--today",
        type=dt.date.fromisoformat,
        default=dt.datetime.now(dt.timezone.utc).date(),
        help="UTC evaluation date (override only for regression tests)",
    )
    args = parser.parse_args()
    seen: set[int] = set()
    try:
        entries = json.loads(args.registry.read_text())["exceptions"]
        if not entries:
            raise ValueError("accepted-exception registry is empty")
        for entry in entries:
            for field in ("owner", "reason", "controls", "exit_condition"):
                if (
                    not isinstance(entry[field], str)
                    or not entry[field].strip()
                ):
                    raise ValueError(f"missing {field}")
            alerts = entry["alerts"]
            if not alerts or any(
                type(n) is not int or n <= 0 or n in seen for n in alerts
            ):
                raise ValueError("invalid or duplicate alert identifiers")
            if len(set(alerts)) != len(alerts):
                raise ValueError("duplicate alert identifiers")
            seen.update(alerts)
            accepted, review, expires = (
                dt.date.fromisoformat(entry[key])
                for key in ("accepted", "review_due", "expires")
            )
            if not accepted <= args.today < review <= expires:
                raise ValueError(
                    f"alerts {alerts}: review overdue or invalid dates"
                )
            if args.today >= expires:
                raise ValueError(f"alerts {alerts}: acceptance expired")
            print(
                f"Alerts {alerts}: review {review}; expiry {expires}; owner {entry['owner']}"
            )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Security exception gate failed: {exc}\n")


if __name__ == "__main__":
    main()
