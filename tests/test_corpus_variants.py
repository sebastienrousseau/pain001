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

"""Bank variants: overlays with patches build their own judged files.

The repository ships public overlays only, so the variant mechanism is
exercised here with an illustrative overlay built in the test: the
shape a reader would write from their own bank's guideline, kept in
their own environment.
"""

from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from pain001.corpus import api
from pain001.corpus.builder import build, deep_merge
from pain001.corpus.registry import load_scenarios, scenario_from
from pain001.corpus.rules import ladder
from pain001.corpus.rules.ladder import applicable_overlays, run_ladder
from pain001.corpus.rules.overlays import load_overlays, overlay_from

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402
import corpus_coverage  # noqa: E402

SCENARIOS = {s.id: s for s in load_scenarios()}
PUBLIC = load_overlays()

EXAMPLE_OVERLAY = {
    "overlay_id": "gb.example.priority",
    "title": "An illustrative priority-payment profile (not a real bank)",
    "applies_to": ["gb.chaps.property-purchase", "gb.international.usd"],
    "versions": ["pain.001.001.03"],
    "source": {
        "title": "Illustrative profile written for the test suite",
        "read": "2026-09-11",
        "access": "public (test fixture)",
    },
    "patch": {
        "payment": {
            "debtor": {
                "address": {
                    "form": "structured",
                    "country_subdivision": "England",
                }
            },
            "type": {"service_level": "URNS"},
        },
        "transactions": {
            "*": {"creditor": {"address": {"form": "structured"}}}
        },
    },
    "patches": {
        "gb.chaps.property-purchase": {
            "transactions": {
                "*": {
                    "creditor": {"address": {"country_subdivision": "England"}}
                }
            }
        }
    },
    "rules": [
        {
            "rule_id": "example-debtor-subdivision",
            "description": "The debtor address carries a country subdivision.",
            "locator": "Dbtr/PstlAdr/CtrySubDvsn",
            "assertion": "required",
            "error_code": "EX_DBTR_SUBDIV",
        },
        {
            "rule_id": "example-service-level",
            "description": "The service level is URNS.",
            "locator": "PmtTpInf/SvcLvl/Cd",
            "assertion": "one_of:[URNS]",
            "error_code": "EX_SVCLVL",
        },
    ],
}


@pytest.fixture
def example():
    """The illustrative patched overlay."""
    return overlay_from(copy.deepcopy(EXAMPLE_OVERLAY))


def test_deep_merge_lists_and_removals() -> None:
    """'*' merges into every list item; None removes a key; refs deep-merge."""
    base = {
        "payment": {
            "batch_booking": True,
            "type": {"service_level": "URGP", "priority": "HIGH"},
        },
        "transactions": [
            {"a": 1, "creditor": {"name": "x", "address": {"town": "T"}}},
            {"a": 2},
        ],
    }
    merged = deep_merge(
        base,
        {
            "payment": {
                "batch_booking": None,
                "type": {"service_level": "URNS"},
            },
            "transactions": {
                "*": {"creditor": {"address": {"form": "structured"}}}
            },
        },
    )
    assert "batch_booking" not in merged["payment"]
    assert merged["payment"]["type"] == {
        "service_level": "URNS",
        "priority": "HIGH",
    }
    assert merged["transactions"][0]["creditor"] == {
        "name": "x",
        "address": {"town": "T", "form": "structured"},
    }
    assert merged["transactions"][1] == {
        "a": 2,
        "creditor": {"address": {"form": "structured"}},
    }
    assert base["payment"]["batch_booking"] is True  # untouched
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    xml = build(
        scenario,
        "pain.001.001.09",
        {
            "payment": {
                "debtor": {"address": {"country_subdivision": "England"}}
            }
        },
    ).xml
    assert (
        "<CtrySubDvsn>England</CtrySubDvsn>" in xml
        and "<TwnNm>London</TwnNm>" in xml
    )


def test_overlay_patch_for_and_has_patch(example) -> None:
    """Per-scenario patches merge over the common patch."""
    public = {o.overlay_id: o for o in PUBLIC}
    assert example.has_patch
    assert not any(o.has_patch for o in PUBLIC), (
        "public overlays are rule-only"
    )
    assert not public["gb.boe.chaps-enhanced-data"].has_patch
    chaps = example.patch_for("gb.chaps.property-purchase")
    assert chaps["payment"]["debtor"]["address"] == {
        "form": "structured",
        "country_subdivision": "England",
    }
    assert (
        chaps["transactions"]["*"]["creditor"]["address"][
            "country_subdivision"
        ]
        == "England"
    )
    usd = example.patch_for("gb.international.usd")
    assert (
        "country_subdivision"
        not in usd["transactions"]["*"]["creditor"]["address"]
    )
    assert example.patch_for("nobody") == example.patch
    plain = overlay_from({"overlay_id": "p", "patches": {"x": {"a": 1}}})
    assert plain.has_patch and plain.patch_for("x") == {"a": 1}
    assert plain.patch_for("y") == {}


def test_applicable_overlays_split_generic_and_variant(example) -> None:
    """Rule-only overlays judge every file; a patched one judges its variant only."""
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    pool = [*PUBLIC, example]
    generic = [o.overlay_id for o in applicable_overlays(scenario, pool)]
    assert generic == ["gb.boe.chaps-enhanced-data"]
    variant = [
        o.overlay_id
        for o in applicable_overlays(scenario, pool, "gb.example.priority")
    ]
    assert variant == ["gb.boe.chaps-enhanced-data", "gb.example.priority"]
    doc = copy.deepcopy(scenario.data)
    doc["overlays"] = ["gb.example.priority"]
    listed = scenario_from(doc)
    assert [o.overlay_id for o in applicable_overlays(listed, pool)] == []
    assert [
        o.overlay_id
        for o in applicable_overlays(listed, pool, "gb.example.priority")
    ] == ["gb.example.priority"]
    assert [
        o.overlay_id for o in build_corpus.variants_for(scenario, pool)
    ] == ["gb.example.priority"]
    assert [o.overlay_id for o in build_corpus.variants_for(listed, pool)] == [
        "gb.example.priority"
    ]
    doc["overlays"] = []
    assert build_corpus.variants_for(scenario_from(doc), pool) == []


def test_shipped_tree_has_no_variants_and_no_bank_names() -> None:
    """Public content only: no variant files, no bank-derived overlay."""
    assert sorted(build_corpus.MARKET_ROOT.rglob("*__*")) == []
    assert all(f.variant is None for f in api.list_files("market"))
    plain = yaml.safe_load(
        build_corpus.target_for(SCENARIOS["gb.fps.single"], "pain.001.001.03")
        .with_suffix(".provenance.yaml")
        .read_text(encoding="utf-8")
    )
    assert plain["variant"] is None


def test_variant_files_are_built_named_and_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example
) -> None:
    """A private overlay builds a variant beside the generic file.

    The build runs into a temporary market root from a temporary
    scenario tree holding one scenario, with the illustrative overlay
    in the pool; the variant carries the patch, is judged by the
    overlay's rules, and the generic file would fail them.
    """
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    shutil.copy(
        SCENARIOS["gb.chaps.property-purchase"].source,
        scenarios / "chaps.yaml",
    )
    market = tmp_path / "market"
    monkeypatch.setattr(
        build_corpus, "load_overlays", lambda: [*PUBLIC, example]
    )
    assert (
        build_corpus.main(
            [
                "--scenarios",
                str(scenarios),
                "--market-root",
                str(market),
                "--skip-coverage",
                "--data-root",
                str(tmp_path),
            ]
        )
        == 0
    )
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    target = build_corpus.target_for(
        scenario, "pain.001.001.03", market, variant=example.overlay_id
    )
    assert target.name == (
        "gb.chaps.property-purchase__gb.example.priority.pain.001.001.03.xml"
    )
    assert target.exists()
    xml = target.read_text(encoding="utf-8")
    assert (
        "<CtrySubDvsn>England</CtrySubDvsn>" in xml and "<Cd>URNS</Cd>" in xml
    )
    generic = build_corpus.target_for(
        scenario, "pain.001.001.03", market
    ).read_text(encoding="utf-8")
    assert "<Cd>URNS</Cd>" not in generic
    record = run_ladder(
        scenario,
        "pain.001.001.03",
        xml,
        [*PUBLIC, example],
        variant=example.overlay_id,
    )
    assert record["overlays"]["gb.example.priority"]["errors"] == 0
    forced = run_ladder(
        scenario,
        "pain.001.001.03",
        generic,
        [example],
        variant=example.overlay_id,
    )
    assert forced["overlays"]["gb.example.priority"]["errors"] >= 1
    sidecar = yaml.safe_load(
        target.with_suffix(".provenance.yaml").read_text(encoding="utf-8")
    )
    assert sidecar["variant"]["overlay"] == "gb.example.priority"
    assert (
        sidecar["variant"]["patch"]["payment"]["type"]["service_level"]
        == "URNS"
    )
    assert not build_corpus.target_for(
        scenario, "pain.001.001.09", market, variant=example.overlay_id
    ).exists(), "a v03 profile builds no .09 variant"

    # the API selects by variant when pointed at that tree
    monkeypatch.setattr(api, "MARKET_ROOT", market)
    files = api.list_files("market")
    assert {f.variant for f in files} == {None, "gb.example.priority"}
    assert "<Cd>URNS</Cd>" in api.get_file(
        "gb.chaps.property-purchase", "pain.001.001.03", "gb.example.priority"
    )
    assert (
        api.provenance(
            "gb.chaps.property-purchase",
            "pain.001.001.03",
            "gb.example.priority",
        )["variant"]["overlay"]
        == "gb.example.priority"
    )
    with pytest.raises(FileNotFoundError):
        api.get_file(
            "gb.chaps.property-purchase",
            "pain.001.001.09",
            "gb.example.priority",
        )
    monkeypatch.setattr(ladder, "load_overlays", lambda: [*PUBLIC, example])
    assert corpus_coverage._ladder_check(sorted(market.rglob("*__*.xml"))) == 0


def test_overlay_versions_limit_variants_and_judgement(example) -> None:
    """A v03 profile builds and judges .03 files only."""
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    assert example.versions == ("pain.001.001.03",)
    pool = [*PUBLIC, example]
    assert [
        o.overlay_id
        for o in build_corpus.variants_for(scenario, pool, "pain.001.001.03")
    ] == ["gb.example.priority"]
    assert build_corpus.variants_for(scenario, pool, "pain.001.001.09") == []
    assert [
        o.overlay_id
        for o in applicable_overlays(
            scenario, pool, "gb.example.priority", "pain.001.001.03"
        )
    ] == ["gb.boe.chaps-enhanced-data", "gb.example.priority"]
    assert [
        o.overlay_id
        for o in applicable_overlays(
            scenario, pool, "gb.example.priority", "pain.001.001.09"
        )
    ] == ["gb.boe.chaps-enhanced-data"]
    assert example.applies(
        "gb.chaps.property-purchase", "priority-payment", "pain.001.001.03"
    )
    assert not example.applies(
        "gb.chaps.property-purchase", "priority-payment", "pain.001.001.09"
    )
    assert example.applies("gb.chaps.property-purchase", "priority-payment")
