#!/usr/bin/env python3
# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Report version drift across the published pain001 suite.

Run in CI on a schedule. It answers one question a user cannot answer
for themselves: do the versions currently on PyPI agree with the
policy in :mod:`pain001.suite`?

The failures it catches, all of which have already happened:

* A **member left behind.** `pain001-lsp` sat at 0.0.54 while the core
  reached 0.0.59. Nothing broke, so nothing said anything.
* A **member claiming a release it predates.** `pain001-loader-xlsx`
  was published as 0.0.54 while requiring `pain001>=0.0.56`, so its own
  number described a suite version older than the core it demands.
* A **floor nobody decided.** The two loaders declared `>=0.0.55` and
  `>=0.0.56`, the wrappers `>=0.0.70`, and no rule said which was right.
  :mod:`pain001.suite` now records the intended floor per member, and a
  published floor that differs from it is reported.
* A **version bumped in the tree and never released.** The tree on
  ``main`` must be the version this repository last published; a bump
  that was never tagged strands whatever it carried (in this family,
  more than once, a security floor) and nothing else notices.

Exits non-zero when the suite disagrees with itself, so the schedule
turns into a notification rather than a report nobody opens.

Usage:
    python scripts/check_suite_consistency.py [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from pain001.suite import CORE, LOCKSTEP, SUITE
except (ImportError, ModuleNotFoundError):
    import importlib.util

    _suite_path = (
        Path(__file__).resolve().parent.parent / "pain001" / "suite.py"
    )
    _spec = importlib.util.spec_from_file_location(
        "pain001.suite", _suite_path
    )
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["pain001.suite"] = _mod
        _spec.loader.exec_module(_mod)
        CORE = _mod.CORE
        LOCKSTEP = _mod.LOCKSTEP
        SUITE = _mod.SUITE
    else:  # pragma: no cover
        raise

#: PyPI JSON API. Documented, cacheable, and needs no credentials.
_PYPI = "https://pypi.org/pypi/{distribution}/json"

#: Give up rather than hang a scheduled job on a slow mirror.
_TIMEOUT_SECONDS = 20

#: The checkout this script belongs to: the core's own tree.
_ROOT = Path(__file__).resolve().parent.parent

#: Published releases whose floor predates the policy. PyPI metadata is
#: immutable, so these can never be corrected, only outlived; each entry
#: names the exact (distribution, version) and the floor it shipped with,
#: and nothing else is waived. A *new* release must follow the policy.
#:
#: * ``0.0.72`` wrappers declared ``>=0.0.71``: they shipped before the
#:   LOCKSTEP floor rule (PR #286).
#: * ``pain001-mcp 0.0.73`` declared ``>=0.0.71``: an out-of-band pyjwt
#:   security release (pain001-mcp #109) that went out before core 0.0.73.
#: * The ``0.0.72`` loaders declared the plugin-contract floors the table
#:   recorded then (``>=0.0.56`` xlsx, ``>=0.0.55`` MT101); every member
#:   is lockstep from 0.0.74.
_PUBLISHED_FLOOR_EXCEPTIONS: dict[tuple[str, str], str] = {
    ("pain001-lsp", "0.0.72"): "0.0.71",
    ("pain001-mcp", "0.0.72"): "0.0.71",
    ("pain001-mcp", "0.0.73"): "0.0.71",
    ("pain001-loader-xlsx", "0.0.72"): "0.0.56",
    ("pain001-loader-mt101", "0.0.72"): "0.0.55",
}


def tree_version(root: Path = _ROOT) -> str:
    """Return the version this checkout declares.

    Read from ``[tool.poetry].version``, the single source of truth, by
    the same one-line match the version-sync CI job uses, so this needs
    no TOML parser on the 3.10 floor.

    Args:
        root: The repository root holding ``pyproject.toml``.

    Returns:
        The declared version string.

    Raises:
        SystemExit: When ``pyproject.toml`` declares no version.
    """
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise SystemExit("pyproject.toml declares no version")
    return match.group(1)


def tree_problems(tree: str, published: str) -> list[str]:
    """Compare this checkout's version with the core's PyPI release.

    Args:
        tree: The version the tree declares, from :func:`tree_version`.
        published: The newest ``pain001`` on PyPI.

    Returns:
        Zero or one problem strings.

    Example:
        >>> tree_problems("0.0.74", "0.0.74")
        []
        >>> tree_problems("0.0.74", "0.0.72")[0][:40]
        'pain001: tree is 0.0.74 but PyPI has 0.0'
    """
    if tree == published:
        return []
    return [
        f"{CORE}: tree is {tree} but PyPI has {published}. Either the "
        f"release was never tagged, or the tree is behind."
    ]


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
    try:
        from packaging.requirements import Requirement
    except ImportError:  # pragma: no cover
        from pip._vendor.packaging.requirements import Requirement

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


def floor_problems(member: Any, version: str, floor: str | None) -> list[str]:
    """Compare a member's published ``pain001`` floor with the policy.

    Args:
        member: The :class:`~pain001.suite.SuiteMember` being checked.
        version: The member's published version.
        floor: The floor it publishes, from :func:`core_floor`.

    Returns:
        Zero or one problem strings.

    Example:
        >>> from pain001.suite import SUITE
        >>> floor_problems(SUITE["pain001-mcp"], "0.0.60", "0.0.60")
        []
        >>> floor_problems(SUITE["pain001-mcp"], "0.0.60", "0.0.55")[0][:38]
        'pain001-mcp 0.0.60 requires pain001>=0'
    """
    policy = member.floor
    if policy is None:
        return []
    expected = version if policy == LOCKSTEP else policy
    if floor == expected:
        return []
    excepted = _PUBLISHED_FLOOR_EXCEPTIONS.get((member.distribution, version))
    if excepted is not None and excepted == floor:
        return []
    why = (
        "every member is lockstep, so the floor is the release itself"
        if policy == LOCKSTEP
        else "this member keeps the floor recorded in pain001.suite; "
        "change it there first"
    )
    return [
        f"{member.distribution} {version} requires {CORE}>="
        f"{floor or '(none)'}, but the suite policy is >={expected}: {why}."
    ]


def audit() -> tuple[list[str], dict[str, Any]]:
    """Compare published versions against the suite policy.

    Returns:
        A tuple of (problems, report). ``problems`` is empty when the
        suite agrees with itself.
    """
    report: dict[str, Any] = {"core": None, "tree": None, "members": {}}
    problems: list[str] = []

    core_info = fetch_metadata(CORE)
    if core_info is None:  # pragma: no cover - core is always published
        return ([f"{CORE} is not published"], report)
    core_version = core_info["version"]
    report["core"] = core_version
    tree = tree_version()
    report["tree"] = tree
    problems.extend(tree_problems(tree, core_version))

    for member in SUITE.values():
        info = fetch_metadata(member.distribution)
        if info is None:
            report["members"][member.distribution] = {"published": None}
            continue

        version = info["version"]
        floor = core_floor(info.get("requires_dist"))
        report["members"][member.distribution] = {
            "published": version,
            "core_floor": floor,
        }

        if version != core_version:
            problems.append(
                f"{member.distribution} is {version}, but every suite "
                f"member must match the core ({core_version}). Release it."
            )

        # The floor must also be reachable. A member requiring a core
        # that was never published is uninstallable no matter how well
        # its own version matches.
        if floor and _as_tuple(floor) > _as_tuple(core_version):
            problems.append(
                f"{member.distribution} requires {CORE}>={floor}, but the "
                f"newest published {CORE} is {core_version}. Nobody can "
                f"install this combination."
            )

        problems.extend(floor_problems(member, version, floor))

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

    print(f"core: {CORE} {report['core']} (tree {report['tree']})")
    for name, data in sorted(report["members"].items()):
        published = data.get("published") or "unpublished"
        floor = data.get("core_floor")
        suffix = f"  (needs {CORE}>={floor})" if floor else ""
        print(f"  {name:<24} {published:<10}{suffix}")

    if problems:
        print("\nSuite is inconsistent:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("\nSuite is consistent.")
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
