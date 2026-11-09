# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Derive component tables from the same inventory as publication checks."""

from __future__ import annotations

from .inventory import inventory

START = "<!-- ecosystem:start -->"
END = "<!-- ecosystem:end -->"


def readme_values() -> dict[str, str]:
    """Build canonical README table substitutions without a second member list."""
    members = inventory()
    rows = [
        f"[{member.project}](https://github.com/{member.repository}) | {member.purpose} | {member.usage}"
        for member in members
    ]
    first = rows[0].split(" | ")
    return {
        "COMPONENT_NAME": first[0],
        "COMPONENT_PURPOSE": first[1],
        "COMPONENT_USE_CASE": first[2] + " |\n| " + " |\n| ".join(rows[1:]),
    }


def roadmap_table(source: str) -> str:
    """Replace only the marked inventory table, preserving roadmap prose."""
    before, remainder = source.split(START, 1)
    _, after = remainder.split(END, 1)
    rows = ["| Component | Role | Publications |", "| :--- | :--- | :--- |"]
    for member in inventory():
        channels = ["GitHub Releases"]
        if member.pypi:
            channels.append("PyPI")
        if member.image:
            channels.append("GHCR")
        if member.runtime:
            channels.append("live website")
        if member.mcp_registry:
            channels.append("MCP Registry")
        rows.append(
            f"| [{member.project}](https://github.com/{member.repository}) | {member.purpose} | {', '.join(channels)} |"
        )
    return before + START + "\n\n" + "\n".join(rows) + "\n\n" + END + after
