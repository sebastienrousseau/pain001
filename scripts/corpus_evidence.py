# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Record external validator runs into a scenario's provenance (D7).

The corpus carries three evidence states: ``hsbc-validated`` (HSBC's
client validation through MyStandards), ``portal-validated`` (the
public SIX and ValidateFin portals) and ``self-validated`` (this
repository's L0 to L3 ladder, which every shipped file passes). The
first two come from outside and are recorded by hand, here, into the
scenario file, the source of truth; the build copies them into every
sidecar the scenario produces.

Usage:
    poetry run python scripts/corpus_evidence.py checklist
    poetry run python scripts/corpus_evidence.py record SCENARIO_ID \\
        --state portal-validated --tool ValidateFin --date 2026-09-12 \\
        --result pass [--note "..."] [--version pain.001.001.09]

``checklist`` prints, per scenario, which external validator the plan
expects and what has been recorded so far. ``record`` appends one
evidence entry to the scenario's ``provenance.evidence``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from pain001.corpus.registry import SCENARIOS_DIR, load_scenarios

STATES = ("hsbc-validated", "portal-validated", "self-validated")
#: Which external validator the plan expects per market (D7).
EXPECTED: dict[str, str] = {
    "GB": "HSBC client validation (MyStandards)",
    "HK": "HSBC client validation (MyStandards)",
    "AE": "HSBC client validation (MyStandards)",
    "QA": "HSBC client validation (MyStandards)",
    "MY": "HSBC client validation (MyStandards)",
    "SG": "HSBC client validation (MyStandards)",
    "CH": "SIX validation portal",
    "DE": "ValidateFin (SEPA)",
    "FR": "ValidateFin (SEPA)",
    "NL": "ValidateFin (SEPA)",
    "BE": "ValidateFin (SEPA)",
    "ES": "ValidateFin (SEPA)",
    "IT": "ValidateFin (SEPA)",
    "LU": "ValidateFin (SEPA)",
}


def checklist(scenarios_dir: Path) -> int:
    """Print the external-evidence checklist.

    Args:
        scenarios_dir: The scenarios directory.

    Returns:
        0 always; the checklist informs, it does not gate.
    """
    for scenario in load_scenarios(scenarios_dir):
        expected = EXPECTED.get(
            scenario.country, "none available (self-validated only)"
        )
        evidence = scenario.data.get("provenance", {}).get("evidence", [])
        recorded = (
            ", ".join(
                f"{e['state']} ({e.get('tool', '?')}, {e.get('date', '?')}: {e.get('result', '?')})"
                for e in evidence
            )
            or "nothing recorded"
        )
        print(f"{scenario.id:<36} expects {expected}; {recorded}")
    return 0


def record(
    scenarios_dir: Path, scenario_id: str, entry: dict[str, str]
) -> int:
    """Append an evidence entry to a scenario file.

    Args:
        scenarios_dir: The scenarios directory.
        scenario_id: The scenario to record against.
        entry: The evidence entry (``state``, ``tool``, ``date``,
            ``result`` and optionally ``note``, ``version``).

    Returns:
        0 when recorded, 1 when the scenario is unknown.
    """
    for scenario in load_scenarios(scenarios_dir):
        if scenario.id != scenario_id or scenario.source is None:
            continue
        document = yaml.safe_load(scenario.source.read_text(encoding="utf-8"))
        provenance = document.setdefault(
            "provenance", {"confidence": "assumed"}
        )
        provenance.setdefault("evidence", []).append(entry)
        scenario.source.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(
            f"recorded {entry['state']} for {scenario_id} in {scenario.source}"
        )
        print(
            "rebuild with scripts/build_corpus.py to carry it into the sidecars"
        )
        return 0
    print(f"no scenario named {scenario_id!r} under {scenarios_dir}")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Run the evidence command.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        The command's exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--scenarios", type=Path, default=SCENARIOS_DIR, help=argparse.SUPPRESS
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("checklist")
    rec = commands.add_parser("record")
    rec.add_argument("scenario_id")
    rec.add_argument("--state", choices=STATES, required=True)
    rec.add_argument("--tool", required=True)
    rec.add_argument("--date", required=True)
    rec.add_argument("--result", required=True)
    rec.add_argument("--note")
    rec.add_argument("--version")
    args = parser.parse_args(argv)
    if args.command == "checklist":
        return checklist(args.scenarios)
    entry = {
        "state": args.state,
        "tool": args.tool,
        "date": args.date,
        "result": args.result,
    }
    if args.note:
        entry["note"] = args.note
    if args.version:
        entry["version"] = args.version
    return record(args.scenarios, args.scenario_id, entry)


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
