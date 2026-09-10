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

"""Scenario documents: schema validation, loading and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from pain001.corpus.registry import (
    SCENARIOS_DIR,
    Scenario,
    ScenarioError,
    load_scenario,
    load_scenarios,
    scenario_from,
    validate_document,
)

MINIMAL = {
    "id": "de.sepa.minimal",
    "family": "sepa-credit-transfer",
    "country": "DE",
    "versions": ["pain.001.001.09"],
    "payment": {
        "debtor": {"name": "A"},
        "debtor_account": {"iban": "auto"},
        "debtor_agent": {"bic": "auto"},
        "requested_execution_date": "2026-01-02",
    },
    "transactions": [
        {
            "end_to_end_id": "E1",
            "amount": {"ccy": "EUR", "value": "1.00"},
            "creditor": {"name": "B"},
            "creditor_account": {"iban": "auto"},
            "creditor_agent": {"bic": "auto"},
        }
    ],
}


def test_bundled_scenarios_load_sorted_and_unique() -> None:
    """The three shipped scenarios load, sorted by id, one family each."""
    scenarios = load_scenarios()
    assert [s.id for s in scenarios] == [
        "de.sepa.sct-salary",
        "gb.chaps.property-purchase",
        "nl.sepa.sdd-core",
    ]
    assert {s.message for s in scenarios} == {"pain.001", "pain.008"}
    assert all(
        s.source and s.source.is_relative_to(SCENARIOS_DIR) for s in scenarios
    )
    assert scenarios[2].seed == 3131


def test_seed_defaults_to_a_stable_hash_of_the_id() -> None:
    """Without ``seed`` the same id always gives the same seed."""
    doc = dict(MINIMAL)
    assert scenario_from(doc).seed == scenario_from(dict(doc)).seed
    assert scenario_from({**doc, "seed": 5}).seed == 5


def test_validate_document_names_the_pointer_and_counts_the_rest() -> None:
    """Errors carry the JSON pointer of the best match and how many more."""
    bad = {**MINIMAL, "country": "Germany", "versions": []}
    with pytest.raises(
        ScenarioError, match=r"<scenario>: at /(country|versions):"
    ) as info:
        validate_document(bad)
    assert "more)" in str(info.value)
    with pytest.raises(
        ScenarioError, match=r"at /transactions/0/amount/value"
    ):
        validate_document(
            {
                **MINIMAL,
                "transactions": [
                    {
                        **MINIMAL["transactions"][0],
                        "amount": {"ccy": "EUR", "value": "1,00"},
                    }
                ],
            }
        )
    with pytest.raises(ScenarioError, match="Additional properties"):
        validate_document({**MINIMAL, "extra": 1})
    validate_document(MINIMAL)


def test_versions_must_share_a_family() -> None:
    """pain.001 and pain.008 editions cannot be mixed in one scenario."""
    with pytest.raises(ScenarioError, match="one message family"):
        scenario_from(
            {**MINIMAL, "versions": ["pain.001.001.09", "pain.008.001.08"]}
        )


def test_load_scenario_reports_yaml_and_shape_errors(tmp_path: Path) -> None:
    """Bad YAML and a non-mapping document both fail with the path."""
    broken = tmp_path / "broken.yaml"
    broken.write_text("id: [unclosed", encoding="utf-8")
    with pytest.raises(ScenarioError, match="not valid YAML"):
        load_scenario(broken)
    listy = tmp_path / "list.yaml"
    listy.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(ScenarioError, match="mapping at the top level"):
        load_scenario(listy)


def test_load_scenarios_rejects_duplicate_ids_and_tolerates_no_dir(
    tmp_path: Path,
) -> None:
    """Two files with one id fail; a missing directory is simply empty."""
    for name in ("a", "b"):
        (tmp_path / f"{name}.yaml").write_text(
            yaml.safe_dump(MINIMAL), encoding="utf-8"
        )
    with pytest.raises(ScenarioError, match="duplicate scenario id"):
        load_scenarios(tmp_path)
    assert load_scenarios(tmp_path / "nope") == []
    loaded = load_scenario(tmp_path / "a.yaml")
    assert (
        isinstance(loaded, Scenario) and loaded.source == tmp_path / "a.yaml"
    )
