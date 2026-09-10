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

"""Scenario documents: what a payment is, validated and discovered.

A scenario is a YAML document conforming to
``pain001/corpus/schema/corpus.schema.json``. It names the payment's
parties, accounts, agents, rail choices and transactions in friendly
keys; :mod:`pain001.corpus.builder` turns it into each ISO edition the
scenario lists. Scenarios live under ``scenarios/`` at the repository
root, the source of truth that is not shipped; the built files are.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml  # type: ignore[import-untyped]

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "corpus.schema.json"
#: The source-of-truth directory in a checkout (absent from the wheel).
SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"


class ScenarioError(ValueError):
    """A scenario document is malformed; the message names where."""


@dataclass(frozen=True)
class Scenario:
    """One validated scenario.

    Attributes:
        id: The scenario id, ``country.rail.name``.
        family: The rail family, e.g. ``priority-payment``.
        country: ISO 3166 alpha-2 market.
        versions: The message types the scenario renders to.
        data: The whole validated document.
        source: Where it was loaded from, if a file.
    """

    id: str
    family: str
    country: str
    versions: tuple[str, ...]
    data: dict[str, Any]
    source: Path | None = None

    @property
    def message(self) -> str:
        """``pain.001`` or ``pain.008``, from the first version."""
        return self.versions[0][:8]

    @property
    def seed(self) -> int:
        """The identifier seed: ``seed`` if given, else a hash of the id."""
        given = self.data.get("seed")
        if given is not None:
            return int(given)
        return (
            sum(ord(ch) * (i + 1) for i, ch in enumerate(self.id)) % 1_000_003
        )


@cache
def schema() -> dict[str, Any]:
    """The scenario JSON schema, loaded once."""
    with open(SCHEMA_PATH, encoding="utf-8") as handle:
        document: dict[str, Any] = json.load(handle)
    return document


def validate_document(document: Any, source: str = "<scenario>") -> None:
    """Check a document against the scenario schema.

    Args:
        document: The parsed YAML/JSON.
        source: A label for error messages, usually the file path.

    Raises:
        ScenarioError: With the JSON pointer and reason of the first
            problem, and the count of others.
    """
    validator = jsonschema.Draft7Validator(schema())
    errors = sorted(
        validator.iter_errors(document), key=lambda e: list(e.absolute_path)
    )
    if not errors:
        return
    first = jsonschema.exceptions.best_match(errors)
    pointer = "/" + "/".join(str(p) for p in first.absolute_path)
    more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
    raise ScenarioError(f"{source}: at {pointer}: {first.message}{more}")


def scenario_from(document: Any, source: Path | None = None) -> Scenario:
    """Validate a document and wrap it.

    Args:
        document: The parsed scenario.
        source: The file it came from, for messages.

    Returns:
        The :class:`Scenario`.

    Raises:
        ScenarioError: If the document fails the schema, or lists
            editions of more than one message family.
    """
    validate_document(document, str(source) if source else "<scenario>")
    mixed = {v[:8] for v in document["versions"]}
    if len(mixed) != 1:
        raise ScenarioError(
            f"{source or '<scenario>'}: versions must belong to one message "
            f"family, got {sorted(mixed)}"
        )
    return Scenario(
        id=document["id"],
        family=document["family"],
        country=document["country"],
        versions=tuple(document["versions"]),
        data=document,
        source=source,
    )


def load_scenario(path: str | Path) -> Scenario:
    """Load and validate one YAML scenario file.

    Args:
        path: The ``.yaml`` file.

    Returns:
        The :class:`Scenario`.

    Raises:
        ScenarioError: If the YAML does not parse or fails the schema.
    """
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ScenarioError(f"{path}: expected a mapping at the top level")
    return scenario_from(document, path)


def load_scenarios(root: str | Path = SCENARIOS_DIR) -> list[Scenario]:
    """Load every ``*.yaml`` under ``root``, sorted by id.

    Args:
        root: The scenarios directory.

    Returns:
        The scenarios; empty when the directory does not exist.

    Raises:
        ScenarioError: If any file is invalid, or two share an id.
    """
    root = Path(root)
    scenarios = [load_scenario(p) for p in sorted(root.rglob("*.yaml"))]
    seen: dict[str, Path | None] = {}
    for scenario in scenarios:
        if scenario.id in seen:
            raise ScenarioError(
                f"duplicate scenario id {scenario.id!r} in "
                f"{seen[scenario.id]} and {scenario.source}"
            )
        seen[scenario.id] = scenario.source
    return sorted(scenarios, key=lambda s: s.id)


__all__ = [
    "SCENARIOS_DIR",
    "SCHEMA_PATH",
    "Scenario",
    "ScenarioError",
    "load_scenario",
    "load_scenarios",
    "scenario_from",
    "schema",
    "validate_document",
]
