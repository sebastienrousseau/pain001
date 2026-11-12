# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The complete family, including members that do not publish on PyPI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

OWNER = "sebastienrousseau"


@dataclass(frozen=True)
class Member:
    """One repository and the channels its release must reach."""

    name: str
    project: str
    purpose: str
    usage: str
    pypi: bool = False
    image: bool = False
    runtime: str = ""
    mcp_registry: str = ""
    required_assets: tuple[str, ...] = ()
    publishers: tuple[str, ...] = ()

    @property
    def repository(self) -> str:
        """Return the repository's owner-qualified name."""
        return f"{OWNER}/{self.name}"


DOCS = Path(__file__).resolve().parents[2] / "docs"


def inventory() -> tuple[Member, ...]:
    """Load the committed publication inventory, core first."""
    source = DOCS / "ecosystem.json"
    records = json.loads(source.read_text())
    for item in records:
        for key in ("required_assets", "publishers"):
            item[key] = tuple(item.get(key, ()))
    return tuple(Member(**item) for item in records)


def unreleased() -> tuple[str, ...]:
    """Name the family's repositories that have no release yet.

    They are declared so that discovery knows them, but have no
    publication to audit until they join ``docs/ecosystem.json`` with
    their first release.
    """
    records = json.loads((DOCS / "ecosystem-unreleased.json").read_text())
    return tuple(item["name"] for item in records)
