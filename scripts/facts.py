#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Write pain001's facts.json: the numbers a release can be described by.

The site and the MCP manifests used to restate counts (message types,
scheme profiles, Python floor) by hand, and they drifted. Every release
now ships ``pain001-<version>.facts.json``, generated from the sources
themselves, and those pages render from it:

* ``version`` and ``python`` from ``[tool.poetry]`` in pyproject.toml;
* ``extras`` from ``[tool.poetry.extras]``;
* ``message_types`` from the template registry;
* ``scheme_profiles``, ``schematron_rulebooks``, ``faces`` and
  ``cli_commands`` from the code that defines them.

Usage::

    python scripts/facts.py [-o FILE] [--check FILE]

``--check`` exits 1 when FILE is not what this tree would write.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: Bumped when a key changes meaning or disappears; new keys do not.
FACTS_VERSION = 1


def _pyproject() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _python_floor(spec: str) -> str:
    """``^3.11`` (Poetry) as ``>=3.11``; other specifiers unchanged."""
    return f">={spec[1:]}" if spec.startswith("^") else spec


def collect() -> dict[str, Any]:
    """Gather the facts from this tree.

    Returns:
        The facts, every list sorted, ready for ``json.dumps``.
    """
    from pain001.cli.cli import cli
    from pain001.faces import available_faces
    from pain001.schematron import PRESET_RULEBOOKS
    from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
    from pain001.validation.schemes import PROFILES

    poetry = _pyproject()["tool"]["poetry"]
    message_types = DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
    commands = sorted(cli.commands)
    return {
        "facts_version": FACTS_VERSION,
        "package": "pain001",
        "version": poetry["version"],
        "python": _python_floor(poetry["dependencies"]["python"]),
        "extras": sorted(poetry["extras"]),
        "message_types": sorted(message_types),
        "scheme_profiles": sorted(PROFILES),
        "schematron_rulebooks": sorted(set(PRESET_RULEBOOKS)),
        "faces": sorted(available_faces()),
        "cli_commands": commands,
        "counts": {
            "message_types": len(message_types),
            "pain001_versions": sum(
                m.startswith("pain.001.") for m in message_types
            ),
            "pain008_versions": sum(
                m.startswith("pain.008.") for m in message_types
            ),
            "scheme_profiles": len(PROFILES),
            "faces": len(available_faces()),
            "cli_commands": len(commands),
        },
    }


def render(facts: dict[str, Any]) -> str:
    """The facts as the file holds them: sorted keys, two-space indent."""
    return json.dumps(facts, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write or check facts.json.

    Args:
        argv: Arguments; ``sys.argv[1:]`` when None.

    Returns:
        0, or 1 when ``--check`` finds a difference.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None)
    args = parser.parse_args(argv)
    text = render(collect())
    if args.check is not None:
        if args.check.read_text(encoding="utf-8") != text:
            print(f"{args.check} is out of date", file=sys.stderr)
            return 1
        print(f"{args.check} is current")
        return 0
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
