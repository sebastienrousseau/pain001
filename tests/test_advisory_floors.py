# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Published advisories stay unreachable, not just unlocked.

A lockfile protects this repository's own CI. It protects nobody who
runs ``pip install pain001[otel]``: their resolver reads the declared
ranges, and a range that admits an affected release will pick one
whenever something else in their environment prefers it. So each
advisory that reaches a dependency pain001 resolves gets a floor in the
manifest, and this file holds every floor in place in three places:
the declared range, the lock, and each hash-pinned requirements file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

if sys.version_info >= (3, 11):  # pragma: no cover - version dependent
    import tomllib
else:  # pragma: no cover - version dependent
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent

#: (package, last affected release, first fixed release, advisory, extra)
#: ``extra`` is the optional feature set through which the package
#: reaches a runtime install; the floor is declared there.
FLOORS = [
    (
        "certifi",
        "2026.7.22",
        "2026.10.19",
        "GHSA-6q48-6c7w-9gw2",
        "otel",
    ),
]


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _declared(name: str) -> SpecifierSet:
    deps = _pyproject()["tool"]["poetry"]["dependencies"]
    assert name in deps, f"{name} has no declared range in pyproject.toml"
    raw = deps[name]
    spec = raw if isinstance(raw, str) else raw["version"]
    return Requirement(f"{name}{spec}").specifier


@pytest.mark.parametrize(
    ("name", "affected", "fixed", "ghsa", "extra"), FLOORS
)
def test_the_declared_range_excludes_the_affected_release(
    name: str, affected: str, fixed: str, ghsa: str, extra: str
) -> None:
    """The range a user's resolver reads cannot pick an affected release."""
    spec = _declared(name)
    assert not spec.contains(Version(affected)), (
        f"{name}{spec} still admits {affected} ({ghsa})"
    )
    assert spec.contains(Version(fixed)), (
        f"{name}{spec} excludes the fix {fixed}"
    )


@pytest.mark.parametrize(
    ("name", "affected", "fixed", "ghsa", "extra"), FLOORS
)
def test_the_floor_ships_with_the_extra_that_pulls_the_package_in(
    name: str, affected: str, fixed: str, ghsa: str, extra: str
) -> None:
    """An optional floor outside every extra is never installed."""
    extras = _pyproject()["tool"]["poetry"]["extras"]
    assert name in extras[extra], (
        f"{name} is not part of the {extra!r} extra, so "
        f"pain001[{extra}] does not apply its {ghsa} floor"
    )


@pytest.mark.parametrize(
    ("name", "affected", "fixed", "ghsa", "extra"), FLOORS
)
def test_the_lock_resolves_a_fixed_release(
    name: str, affected: str, fixed: str, ghsa: str, extra: str
) -> None:
    """CI installs from the lock, so the lock must be past the fix."""
    with (ROOT / "poetry.lock").open("rb") as handle:
        lock = tomllib.load(handle)
    versions = [p["version"] for p in lock["package"] if p["name"] == name]
    assert versions, f"{name} is not in poetry.lock"
    for version in versions:
        assert Version(version) >= Version(fixed), (
            f"poetry.lock pins {name} {version}, affected by {ghsa}"
        )


def _requirement_files() -> list[Path]:
    files = [ROOT / "requirements.txt"]
    files += sorted((ROOT / ".github" / "requirements").glob("*.txt"))
    return files


@pytest.mark.parametrize(
    ("name", "affected", "fixed", "ghsa", "extra"), FLOORS
)
def test_every_hash_pinned_file_is_past_the_fix(
    name: str, affected: str, fixed: str, ghsa: str, extra: str
) -> None:
    """The CI tool sets (docs, SBOM, fuzz) install from these files."""
    pin = re.compile(rf"^{re.escape(name)}==(\S+)", re.MULTILINE)
    stale = []
    for path in _requirement_files():
        for version in pin.findall(path.read_text(encoding="utf-8")):
            if Version(version) < Version(fixed):
                stale.append(f"{path.relative_to(ROOT)}: {name}=={version}")
    assert not stale, f"pinned below the {ghsa} fix {fixed}: {stale}"
