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

"""The validation ladder, the evidence workflow and the L2/L3 gate."""

from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from pain001.corpus.builder import build
from pain001.corpus.registry import (
    SCENARIOS_DIR,
    load_scenarios,
    scenario_from,
)
from pain001.corpus.rules.ladder import ladder_passes, run_ladder
from pain001.corpus.rules.overlays import load_overlays

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402
import corpus_coverage  # noqa: E402
import corpus_evidence  # noqa: E402

SCENARIOS = {s.id: s for s in load_scenarios()}


def test_ladder_record_for_the_chaps_scenario() -> None:
    """All four rungs report, every one clean, overlays chosen by family."""
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    assert scenario.profiles == (
        "uk-chaps",
        "purpose-mandate-gb",
        "anti-duplicate",
    )
    assert scenario.overlays is None
    xml = build(scenario, "pain.001.001.09").xml
    record = run_ladder(scenario, "pain.001.001.09", xml)
    assert record["xsd"] == {"errors": 0, "findings": []}
    assert record["mdr"] == {"errors": 0, "findings": []}
    assert set(record["profiles"]) == set(scenario.profiles)
    assert list(record["overlays"]) == ["gb.boe.chaps-enhanced-data"]
    assert ladder_passes(record)
    # an explicit overlay list replaces applies_to, and an unknown id is simply absent
    doc = copy.deepcopy(scenario.data)
    doc["overlays"] = ["nope"]
    explicit = scenario_from(doc)
    assert explicit.overlays == ("nope",)
    assert (
        run_ladder(explicit, "pain.001.001.09", xml, load_overlays())[
            "overlays"
        ]
        == {}
    )
    doc["overlays"] = ["gb.boe.chaps-enhanced-data"]
    assert list(
        run_ladder(scenario_from(doc), "pain.001.001.09", xml)["overlays"]
    ) == ["gb.boe.chaps-enhanced-data"]


def test_ladder_reports_failures_on_every_rung() -> None:
    """A tampered file fails L2 and L3; each rung flips ladder_passes."""
    scenario = SCENARIOS["gb.chaps.property-purchase"]
    xml = build(scenario, "pain.001.001.09").xml
    tampered = xml.replace('Ccy="GBP"', 'Ccy="USD"').replace(
        "<Cd>HLST</Cd>", "<Cd>SUPP</Cd>"
    )
    record = run_ladder(scenario, "pain.001.001.09", tampered)
    assert record["profiles"]["uk-chaps"]["errors"] >= 1
    assert record["profiles"]["uk-chaps"]["findings"][0].startswith(
        "UK-CHAPS-CCY"
    )
    assert record["overlays"]["gb.boe.chaps-enhanced-data"]["warnings"] == 1
    assert not ladder_passes(record)
    clean = run_ladder(scenario, "pain.001.001.09", xml)
    for rung, key in (
        ("xsd", None),
        ("mdr", None),
        ("profiles", "uk-chaps"),
        ("overlays", "gb.boe.chaps-enhanced-data"),
    ):
        broken = copy.deepcopy(clean)
        if key is None:
            broken[rung]["errors"] = 1
        else:
            broken[rung][key]["errors"] = 1
        assert not ladder_passes(broken), rung
    assert ladder_passes(clean)
    warned = copy.deepcopy(clean)
    warned["profiles"]["uk-chaps"]["warnings"] = 3
    assert ladder_passes(warned)


def test_build_refuses_a_file_that_fails_the_ladder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing rung is a build error, so the file is never shipped."""
    scenario = SCENARIOS["de.sepa.sct-salary"]
    result = build(scenario, "pain.001.001.09")
    assert "validation:" in build_corpus.provenance_for(scenario, result)
    monkeypatch.setattr(build_corpus, "ladder_passes", lambda record: False)
    with pytest.raises(SystemExit, match="fails the validation ladder"):
        build_corpus.provenance_for(scenario, result)


def test_gate_l2_l3_on_market_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate re-runs the ladder on market files and names what failed."""
    market = build_corpus.MARKET_ROOT
    files = sorted(market.rglob("*.xml"))
    assert corpus_coverage._ladder_check(files) == 0
    sandbox = tmp_path / "market"
    shutil.copytree(market, sandbox)
    victim = next(sandbox.rglob("gb.chaps*09.xml"))
    victim.write_text(
        victim.read_text(encoding="utf-8").replace('Ccy="GBP"', 'Ccy="USD"'),
        encoding="utf-8",
    )
    stranger = sandbox / "xx" / "zz.unknown.pain.001.001.09.xml"
    stranger.parent.mkdir()
    stranger.write_text(victim.read_text(encoding="utf-8"), encoding="utf-8")
    assert corpus_coverage._ladder_check(sorted(sandbox.rglob("*.xml"))) == 2
    out = capsys.readouterr().out
    assert "no scenario named 'zz.unknown'" in out
    assert "UK-CHAPS-CCY" in out and "'profiles'" in out
    record = {
        "xsd": {"errors": 1, "findings": ["x"]},
        "mdr": {"errors": 0, "findings": []},
        "profiles": {},
        "overlays": {"o": {"errors": 2, "findings": ["y"]}},
    }
    assert corpus_coverage._failed_rungs(record) == {
        "xsd": ["x"],
        "overlays": {"o": ["y"]},
    }


def test_evidence_checklist_and_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The checklist names the expected validator; record appends to the file."""
    scenarios = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS_DIR, scenarios)
    assert (
        corpus_evidence.main(["--scenarios", str(scenarios), "checklist"]) == 0
    )
    out = capsys.readouterr().out
    assert (
        "gb.chaps.property-purchase" in out and "HSBC client validation" in out
    )
    assert (
        "de.sepa.sct-salary" in out
        and "ValidateFin" in out
        and "nothing recorded" in out
    )
    argv = [
        "--scenarios",
        str(scenarios),
        "record",
        "de.sepa.sct-salary",
        "--state",
        "portal-validated",
        "--tool",
        "ValidateFin",
        "--date",
        "2026-09-12",
        "--result",
        "pass",
        "--note",
        "SCT 2025",
        "--version",
        "pain.001.001.09",
    ]
    assert corpus_evidence.main(argv) == 0
    assert "recorded portal-validated" in capsys.readouterr().out
    document = yaml.safe_load(
        (scenarios / "de" / "sepa.sct-salary.yaml").read_text(encoding="utf-8")
    )
    assert document["provenance"]["evidence"] == [
        {
            "state": "portal-validated",
            "tool": "ValidateFin",
            "date": "2026-09-12",
            "result": "pass",
            "note": "SCT 2025",
            "version": "pain.001.001.09",
        }
    ]
    assert (
        corpus_evidence.main(["--scenarios", str(scenarios), "checklist"]) == 0
    )
    assert (
        "portal-validated (ValidateFin, 2026-09-12: pass)"
        in capsys.readouterr().out
    )
    assert (
        corpus_evidence.main(
            [
                "--scenarios",
                str(scenarios),
                "record",
                "xx.none",
                "--state",
                "self-validated",
                "--tool",
                "t",
                "--date",
                "d",
                "--result",
                "r",
            ]
        )
        == 1
    )
    assert "no scenario named 'xx.none'" in capsys.readouterr().out
    # a scenario without provenance gets one
    bare = scenarios / "de" / "bare.yaml"
    doc = yaml.safe_load(
        (scenarios / "de" / "sepa.sct-salary.yaml").read_text(encoding="utf-8")
    )
    doc["id"] = "de.sepa.bare"
    doc.pop("provenance")
    bare.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    assert (
        corpus_evidence.main(
            [
                "--scenarios",
                str(scenarios),
                "record",
                "de.sepa.bare",
                "--state",
                "self-validated",
                "--tool",
                "pain001",
                "--date",
                "2026-09-12",
                "--result",
                "pass",
            ]
        )
        == 0
    )
    assert (
        yaml.safe_load(bare.read_text(encoding="utf-8"))["provenance"][
            "confidence"
        ]
        == "assumed"
    )
