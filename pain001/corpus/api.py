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

"""The shipped corpus, from the installed package.

Everything under ``pain001/corpus/data`` ships in the wheel: the market
files with their provenance sidecars and the coverage sets with their
reports. These functions read them without a checkout, which is what
the suite's other members (the MCP server, the LSP, the website build)
need.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

DATA_ROOT = Path(__file__).resolve().parent / "data"
MARKET_ROOT = DATA_ROOT / "market"
COVERAGE_ROOT = DATA_ROOT / "coverage"


@dataclass(frozen=True)
class CorpusFile:
    """One shipped XML file.

    Attributes:
        kind: ``market`` or ``coverage``.
        version: The message type.
        path: Where the file is.
        scenario_id: The scenario, for market files.
        country: ISO 3166 alpha-2, for market files.
        family: The rail family, for market files.
    """

    kind: str
    version: str
    path: Path
    scenario_id: str | None = None
    country: str | None = None
    family: str | None = None

    def read(self) -> str:
        """The file's text."""
        return self.path.read_text(encoding="utf-8")


def list_files(kind: str | None = None) -> list[CorpusFile]:
    """Every shipped corpus file: market files, then coverage sets, each by path.

    Args:
        kind: ``market``, ``coverage`` or ``None`` for both.

    Returns:
        The files.
    """
    files: list[CorpusFile] = []
    if kind in (None, "market") and MARKET_ROOT.is_dir():
        for path in sorted(MARKET_ROOT.rglob("*.xml")):
            scenario_id, _, rest = path.name.partition(".pain.")
            files.append(
                CorpusFile(
                    "market",
                    "pain." + rest[: -len(".xml")],
                    path,
                    scenario_id,
                    path.parent.parent.name.upper(),
                    path.parent.name,
                )
            )
    if kind in (None, "coverage") and COVERAGE_ROOT.is_dir():
        for path in sorted(COVERAGE_ROOT.rglob("set-*.xml")):
            files.append(CorpusFile("coverage", path.parent.name, path))
    return files


def get_file(scenario_id: str, version: str) -> str:
    """The text of one market file.

    Args:
        scenario_id: The scenario, e.g. ``gb.chaps.property-purchase``.
        version: The message type, e.g. ``pain.001.001.09``.

    Returns:
        The XML text.

    Raises:
        FileNotFoundError: If the scenario has no file for that edition.
    """
    for entry in list_files("market"):
        if entry.scenario_id == scenario_id and entry.version == version:
            return entry.read()
    raise FileNotFoundError(f"no market file for {scenario_id} in {version}")


def provenance(scenario_id: str, version: str) -> dict[str, Any]:
    """The provenance sidecar of one market file, parsed.

    Args:
        scenario_id: The scenario.
        version: The message type.

    Returns:
        The sidecar: sources, confidence, evidence, build report,
        validation ladder and SHA-256.

    Raises:
        FileNotFoundError: If the scenario has no file for that edition.
    """
    for entry in list_files("market"):
        if entry.scenario_id == scenario_id and entry.version == version:
            sidecar = entry.path.with_suffix(".provenance.yaml")
            data: dict[str, Any] = yaml.safe_load(
                sidecar.read_text(encoding="utf-8")
            )
            return data
    raise FileNotFoundError(f"no market file for {scenario_id} in {version}")


def coverage_report(version: str) -> dict[str, Any]:
    """The shipped coverage verdict of one edition.

    Args:
        version: The message type.

    Returns:
        The ``coverage.json`` content: sources, path and branch counts
        and percentages, completeness, missing and exempt lists.

    Raises:
        FileNotFoundError: If the edition has no coverage set.
    """
    path = COVERAGE_ROOT / version / "coverage.json"
    if not path.exists():
        raise FileNotFoundError(f"no coverage set for {version}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


__all__ = [
    "COVERAGE_ROOT",
    "DATA_ROOT",
    "MARKET_ROOT",
    "CorpusFile",
    "coverage_report",
    "get_file",
    "list_files",
    "provenance",
]
