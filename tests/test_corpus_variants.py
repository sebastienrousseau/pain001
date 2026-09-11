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

"""Bank variants: overlays with patches build their own judged files."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from pain001.corpus import api
from pain001.corpus.builder import build, deep_merge
from pain001.corpus.registry import load_scenarios, scenario_from
from pain001.corpus.rules.ladder import applicable_overlays, run_ladder
from pain001.corpus.rules.overlays import load_overlays, overlay_from

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402
import corpus_coverage  # noqa: E402

SCENARIOS = {s.id: s for s in load_scenarios()}
OVERLAYS = {o.overlay_id: o for o in load_overlays()}


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


def test_overlay_patch_for_and_has_patch() -> None:
    """Per-scenario patches merge over the common patch."""
    overlay = OVERLAYS["gb.hsbc.priority"]
    assert (
        overlay.has_patch
        and not OVERLAYS["gb.boe.chaps-enhanced-data"].has_patch
    )
    chaps = overlay.patch_for("gb.chaps.property-purchase")
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
    usd = overlay.patch_for("gb.international.usd")
    assert (
        "country_subdivision"
        not in usd["transactions"]["*"]["creditor"]["address"]
    )
    assert overlay.patch_for("nobody") == overlay.patch
    plain = overlay_from({"overlay_id": "p", "patches": {"x": {"a": 1}}})
    assert (
        plain.has_patch
        and plain.patch_for("x") == {"a": 1}
        and plain.patch_for("y") == {}
    )


def test_applicable_overlays_split_generic_and_variant() -> None:
    """Rule-only overlays judge every file; a patched one judges its variant only."""
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    pool = list(OVERLAYS.values())
    generic = [o.overlay_id for o in applicable_overlays(scenario, pool)]
    assert generic == ["gb.boe.chaps-enhanced-data"]
    variant = [
        o.overlay_id
        for o in applicable_overlays(scenario, pool, "gb.hsbc.priority")
    ]
    assert variant == ["gb.boe.chaps-enhanced-data", "gb.hsbc.priority"]
    doc = copy.deepcopy(scenario.data)
    doc["overlays"] = ["gb.hsbc.priority"]
    listed = scenario_from(doc)
    assert [o.overlay_id for o in applicable_overlays(listed, pool)] == []
    assert [
        o.overlay_id
        for o in applicable_overlays(listed, pool, "gb.hsbc.priority")
    ] == ["gb.hsbc.priority"]
    assert [
        o.overlay_id for o in build_corpus.variants_for(scenario, pool)
    ] == ["gb.hsbc.priority"]
    assert [o.overlay_id for o in build_corpus.variants_for(listed, pool)] == [
        "gb.hsbc.priority"
    ]
    doc["overlays"] = []
    assert build_corpus.variants_for(scenario_from(doc), pool) == []


def test_variant_files_are_built_named_and_judged() -> None:
    """The HSBC variants exist, carry the patch, and pass their own rules."""
    scenario = SCENARIOS["gb.fps.single"]
    overlay = OVERLAYS["gb.hsbc.faster-payments"]
    target = build_corpus.target_for(
        scenario, "pain.001.001.03", variant=overlay.overlay_id
    )
    assert (
        target.name
        == "gb.fps.single__gb.hsbc.faster-payments.pain.001.001.03.xml"
    )
    assert target.exists()
    xml = target.read_text(encoding="utf-8")
    assert "<Cd>URNS</Cd>" in xml and "<ChrgBr>SHAR</ChrgBr>" in xml
    generic = build_corpus.target_for(scenario, "pain.001.001.03").read_text(
        encoding="utf-8"
    )
    assert "<Cd>URGP</Cd>" in generic
    record = run_ladder(
        scenario, "pain.001.001.03", xml, variant=overlay.overlay_id
    )
    assert record["overlays"]["gb.hsbc.faster-payments"]["errors"] == 0
    # the generic file would fail the HSBC rules, which is why it is a variant
    forced = run_ladder(
        scenario,
        "pain.001.001.03",
        generic,
        [overlay],
        variant=overlay.overlay_id,
    )
    assert forced["overlays"]["gb.hsbc.faster-payments"]["errors"] >= 1
    sidecar = yaml.safe_load(
        target.with_suffix(".provenance.yaml").read_text(encoding="utf-8")
    )
    assert sidecar["variant"]["overlay"] == "gb.hsbc.faster-payments"
    assert (
        sidecar["variant"]["patch"]["payment"]["type"]["service_level"]
        == "URNS"
    )
    assert "restricted" in sidecar["variant"]["source"]["access"]
    plain = yaml.safe_load(
        build_corpus.target_for(scenario, "pain.001.001.03")
        .with_suffix(".provenance.yaml")
        .read_text(encoding="utf-8")
    )
    assert plain["variant"] is None


def test_api_and_gate_understand_variants() -> None:
    """list_files exposes the variant; get_file and provenance select by it."""
    market = api.list_files("market")
    variants = [f for f in market if f.variant]
    assert {f.variant for f in variants} >= {
        "gb.hsbc.faster-payments",
        "gb.hsbc.bacs",
        "gb.hsbc.priority",
        "gb.hsbc.direct-debit",
        "eu.hsbc.sepa-credit-transfer",
    }
    hsbc = api.get_file(
        "gb.fps.single", "pain.001.001.03", "gb.hsbc.faster-payments"
    )
    assert "<Cd>URNS</Cd>" in hsbc and "<Cd>URNS</Cd>" not in api.get_file(
        "gb.fps.single", "pain.001.001.03"
    )
    assert (
        api.provenance(
            "gb.fps.single", "pain.001.001.03", "gb.hsbc.faster-payments"
        )["variant"]["overlay"]
        == "gb.hsbc.faster-payments"
    )
    with pytest.raises(FileNotFoundError):
        api.get_file(
            "gb.fps.single", "pain.001.001.09", "gb.hsbc.faster-payments"
        )  # a v03 guideline, no .09 variant
    files = sorted(build_corpus.MARKET_ROOT.rglob("*__*.xml"))
    assert len(files) == 19
    assert corpus_coverage._ladder_check(files) == 0


def test_overlay_versions_limit_variants_and_judgement() -> None:
    """A v03 guideline builds and judges .03 files only."""
    scenario = SCENARIOS["gb.fps.single"]
    overlay = OVERLAYS["gb.hsbc.faster-payments"]
    assert overlay.versions == ("pain.001.001.03",)
    pool = list(OVERLAYS.values())
    assert [
        o.overlay_id
        for o in build_corpus.variants_for(scenario, pool, "pain.001.001.03")
    ] == ["gb.hsbc.faster-payments"]
    assert build_corpus.variants_for(scenario, pool, "pain.001.001.09") == []
    assert [
        o.overlay_id
        for o in applicable_overlays(
            scenario, pool, "gb.hsbc.faster-payments", "pain.001.001.03"
        )
    ] == ["gb.hsbc.faster-payments"]
    assert (
        applicable_overlays(
            scenario, pool, "gb.hsbc.faster-payments", "pain.001.001.09"
        )
        == []
    )
    assert overlay.applies(
        "gb.fps.single", "faster-payment", "pain.001.001.03"
    )
    assert not overlay.applies(
        "gb.fps.single", "faster-payment", "pain.001.001.09"
    )
    assert overlay.applies(
        "gb.fps.single", "faster-payment"
    )  # version unknown: not filtered
    assert not build_corpus.target_for(
        scenario, "pain.001.001.09", variant=overlay.overlay_id
    ).exists()
