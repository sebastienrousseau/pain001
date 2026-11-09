# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Collect failures across the full inventory without hiding partial releases."""

from __future__ import annotations

import re
from typing import Any

from .channels import (
    image_evidence,
    mcp_registry_evidence,
    pypi_evidence,
    website_evidence,
)
from .inventory import Member, inventory
from .releases import API, release_evidence, require
from .transport import Client, Transport

DISCOVERY = "https://api.github.com/search/repositories?q=user:sebastienrousseau+pain001+in:name&per_page=100"


def discover(client: Transport, members: tuple[Member, ...]) -> None:
    """Reject a newly added or silently omitted active repository."""
    result = client.json(DISCOVERY)
    require(
        result["total_count"] <= 100, "inventory discovery requires pagination"
    )
    names = {item["name"] for item in result["items"] if not item["archived"]}
    require(
        names == {member.name for member in members},
        "inventory differs from active GitHub repositories",
    )


def member_evidence(
    client: Transport, member: Member, version: str, latest: bool
) -> dict[str, Any]:
    """Inspect the channels this member actually publishes to."""
    result = release_evidence(client, member, version, latest)
    if member.pypi:
        result.update(
            pypi_evidence(
                client, member, version, latest, result["asset_hashes"]
            )
        )
    if member.image:
        result.update(
            image_evidence(client, member, version, result["commit"])
        )
    if member.runtime:
        result.update(website_evidence(client, member, version, latest))
    if member.mcp_registry:
        result.update(mcp_registry_evidence(client, member, version, latest))
    return result


def audit(
    client: Transport | None = None, version: str | None = None
) -> dict[str, Any]:
    """Return publication evidence and every observed member failure.

    Without a version, audit the latest published core and require every
    other member's latest release to match. Explicit versions select their
    immutable tags and PyPI metadata, while containers and the website are
    still checked live.
    """
    client = Client() if client is None else client
    members = inventory()
    report: dict[str, Any] = {
        "version": version,
        "complete": False,
        "members": {},
        "problems": [],
    }
    latest = version is None
    try:
        chosen = (
            client.json(API + members[0].repository + "/releases/latest")[
                "tag_name"
            ]
            if latest
            else version
        )
        if not isinstance(chosen, str):
            raise ValueError("release tag must be a version string")
        chosen = chosen.removeprefix("v")
        require(
            bool(
                re.fullmatch(
                    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", chosen
                )
            ),
            "invalid stable release version",
        )
        report["version"] = chosen
    except (ValueError, KeyError, TypeError, IndexError) as error:
        report["problems"].append(
            f"pain001: cannot establish release version: {error}"
        )
        return report
    try:
        discover(client, members)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        report["problems"].append(f"inventory: {error}")
    for member in members:
        try:
            report["members"][member.name] = member_evidence(
                client, member, chosen, latest
            )
        except (ValueError, KeyError, TypeError, IndexError) as error:
            report["problems"].append(f"{member.name}: {error}")
            report["members"][member.name] = {"error": str(error)}
    report["complete"] = not report["problems"]
    return report
