# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate companion audit workflows pinned to one reviewed core commit."""

from __future__ import annotations

import argparse
import json
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
  workflow_run:
    workflows: __PUBLISHERS__
    types: [completed]
permissions:
  contents: read
concurrency:
  group: suite-consistency
  cancel-in-progress: true
jobs:
  consistency:
    name: All nine publications agree
    if: >-
      github.event_name != 'workflow_run' ||
      (github.event.workflow_run.conclusion == 'success' &&
       github.event.workflow_run.event == 'push' &&
       (startsWith(github.event.workflow_run.head_branch, 'v0.')__DEPLOY_TRIGGER__))
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
    """Pin one companion to immutable code and its actual publication events."""
    if not re.fullmatch(r"[0-9a-f]{40}", core_ref):
        raise ValueError("core-ref must be a full immutable commit SHA")
    deployment = ""
    if member.runtime:
        deployment = " || (github.event.workflow_run.head_branch == 'main' && github.event.workflow_run.name == 'CI')"
    return (
        TEMPLATE.replace("__CORE_REF__", core_ref)
        .replace(
            "__PUBLISHERS__", json.dumps(member.publishers, ensure_ascii=False)
        )
        .replace("__DEPLOY_TRIGGER__", deployment)
    )


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
