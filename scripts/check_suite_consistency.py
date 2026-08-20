#!/usr/bin/env python3
# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Report version drift across the published pain001 suite.

Run in CI on a schedule. It answers one question a user cannot answer
for themselves: do the versions currently on PyPI agree with the
policy in :mod:`pain001.suite`?

Two failures it catches, both of which have already happened:

* A **lockstep member left behind.** `pain001-lsp` sat at 0.0.54 while
  the core reached 0.0.59. Nothing broke, so nothing said anything.
* A **plugin claiming a release it predates.** `pain001-loader-xlsx`
  was published as 0.0.54 while requiring `pain001>=0.0.56`, so its own
  number described a suite version older than the core it demands.

Exits non-zero when the suite disagrees with itself, so the schedule
turns into a notification rather than a report nobody opens.

Usage:
    python scripts/check_suite_consistency.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

from pain001.suite import CORE, SUITE

#: PyPI JSON API. Documented, cacheable, and needs no credentials.
_PYPI = "https://pypi.org/pypi/{distribution}/json"

#: Give up rather than hang a scheduled job on a slow mirror.
_TIMEOUT_SECONDS = 20


def fetch_metadata(distribution: str) -> dict[str, Any] | None:
    """Return the PyPI metadata for ``distribution``.

    Args:
        distribution: Distribution name as published.

    Returns:
        The parsed ``info`` block, or ``None`` when the distribution is
        not published yet.
    """
    url = _PYPI.format(distribution=distribution)
    try:
        with urllib.request.urlopen(  # noqa: S310 - fixed https host
            url, timeout=_TIMEOUT_SECONDS
        ) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    info: dict[str, Any] = payload["info"]
    return info


def core_floor(requires_dist: list[str] | None) -> str | None:
    """Return the minimum ``pain001`` a distribution declares.

    Parsed with :mod:`packaging`, not by scanning for ``>=``. Real
    metadata puts the specifiers in any order — ``pain001<1,>=0.0.56``
    is what the plugins actually publish — and a hand-rolled scan reads
    that as "no floor", which silently disables the very check this
    function feeds.

    Args:
        requires_dist: The distribution's ``Requires-Dist`` entries.

    Returns:
        The floor version as a string, or ``None`` when the
        distribution declares no lower bound on the core.

    Example:
        >>> core_floor(["pain001<1,>=0.0.56", "openpyxl>=3.1"])
        '0.0.56'
        >>> core_floor(["pain001<1"]) is None
        True
    """
    from packaging.requirements import Requirement

    for entry in requires_dist or []:
        try:
            requirement = Requirement(entry)
        except Exception:  # noqa: BLE001 - tolerate odd metadata
            continue
        if requirement.name != CORE:
            continue
        floors = [
            spec.version
            for spec in requirement.specifier
            if spec.operator in (">=", "==", "~=")
        ]
        if not floors:
            return None
        return max(floors, key=_as_tuple)
    return None


def _as_tuple(version: str) -> tuple[int, ...]:
    """Return ``version`` as a comparable tuple, ignoring suffixes.

    Args:
        version: A dotted version string.

    Returns:
        Its numeric components.
    """
    parts: list[int] = []
    for chunk in version.split("."):
        # Stop at the first non-digit rather than filtering them out:
        # "60rc1" is release-candidate 1 of 60, and squeezing the digits
        # together yields 601, which sorts an rc *above* ten releases
        # that follow it.
        digits = ""
        for character in chunk:
            if not character.isdigit():
                break
            digits += character
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def audit() -> tuple[list[str], dict[str, Any]]:
    """Compare published versions against the suite policy.

    Returns:
        A tuple of (problems, report). ``problems`` is empty when the
        suite agrees with itself.
    """
    report: dict[str, Any] = {"core": None, "members": {}}
    problems: list[str] = []

    core_info = fetch_metadata(CORE)
    if core_info is None:  # pragma: no cover - core is always published
        return ([f"{CORE} is not published"], report)
    core_version = core_info["version"]
    report["core"] = core_version

    for member in SUITE.values():
        info = fetch_metadata(member.distribution)
        if info is None:
            report["members"][member.distribution] = {"published": None}
            continue

        version = info["version"]
        floor = core_floor(info.get("requires_dist"))
        report["members"][member.distribution] = {
            "published": version,
            "lockstep": member.lockstep,
            "core_floor": floor,
        }

        if member.lockstep and version != core_version:
            problems.append(
                f"{member.distribution} is {version}, but lockstep members "
                f"must match the core ({core_version}). Release it, or "
                f"move it out of lockstep in pain001/suite.py."
            )

        # A plugin's own version is deliberately *not* compared to the
        # core's. Plugins number independently, so `0.0.2` requiring
        # `pain001>=0.0.55` is correct, not drift — an earlier version
        # of this check flagged exactly that and was wrong.
        #
        # What does matter is that the floor is reachable: a plugin
        # requiring a core that was never published is uninstallable.
        if floor and _as_tuple(floor) > _as_tuple(core_version):
            problems.append(
                f"{member.distribution} requires {CORE}>={floor}, but the "
                f"newest published {CORE} is {core_version}. Nobody can "
                f"install this combination."
            )

    return problems, report


def main(argv: list[str] | None = None) -> int:
    """Run the audit and report.

    Args:
        argv: Command-line arguments, for testing.

    Returns:
        ``0`` when the suite is consistent, ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit the raw report"
    )
    args = parser.parse_args(argv)

    problems, report = audit()

    if args.json:
        # JSON only. Appending prose makes the output unparseable for
        # the thing that consumes it.
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if problems else 0

    if True:
        print(f"core: {CORE} {report['core']}")
        for name, data in sorted(report["members"].items()):
            published = data.get("published") or "unpublished"
            kind = "lockstep" if data.get("lockstep") else "plugin"
            floor = data.get("core_floor")
            suffix = f", needs {CORE}>={floor}" if floor else ""
            print(f"  {name:<24} {published:<10} ({kind}{suffix})")

    if problems:
        print("\nSuite is inconsistent:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("\nSuite is consistent.")
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
