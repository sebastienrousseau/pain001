# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate companion audit workflows pinned to one reviewed core commit."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from .inventory import Member, inventory

TEMPLATE = """# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
# Generated from the core's docs/ecosystem.json by render_ecosystem_workflows.py.
name: Suite Consistency
on:
  schedule:
    - cron: "59 6 * * *"
  workflow_dispatch:
    inputs:
      version:
        description: "Explicit suite version; empty checks the latest published family"
        type: string
        default: ""
permissions:
  contents: read
concurrency:
  group: suite-consistency
  cancel-in-progress: true
jobs:
  consistency:
    name: All nine publications agree
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: sebastienrousseau/pain001/.github/actions/check-ecosystem@__CORE_REF__
        with:
          version: ${{ inputs.version }}
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        with:
          name: ecosystem-publication-report
          path: ecosystem-publication.json
          if-no-files-found: error
          retention-days: 14
"""


def render(member: Member, core_ref: str) -> str:
    """Pin one companion's audit to an immutable, reviewed core commit.

    The audit runs daily and on dispatch, never on another workflow's
    completion: a ``workflow_run`` trigger runs with the default
    branch's trust whatever started it, which is the class of trigger
    the core's own workflows no longer use. Every companion renders
    the same file; ``member`` names the repository it is written for.
    """
    del member
    if not re.fullmatch(r"[0-9a-f]{40}", core_ref):
        raise ValueError("core-ref must be a full immutable commit SHA")
    return TEMPLATE.replace("__CORE_REF__", core_ref)


def main(argv: list[str] | None = None) -> int:
    """Write all eight companion workflows into a review directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--core-ref",
        required=True,
        help="reviewed core commit containing the action",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="directory for the eight repository trees",
    )
    args = parser.parse_args(argv)
    for member in inventory()[1:]:
        rendered = render(member, args.core_ref)
        target = (
            args.out / member.name / ".github/workflows/suite-consistency.yml"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(f"Generated eight companion workflows pinned to {args.core_ref}")
    return 0
