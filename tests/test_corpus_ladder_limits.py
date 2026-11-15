# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""The ladder's overlay choice, its counts and its five-finding excerpts.

A ladder record keeps the first five findings of each rung and counts
errors and warnings apart. These tests feed it a file that fails many
times over and a pool of overlays built in the test, so which overlay
judges which file, and what the record says, is checked exactly.
"""

from __future__ import annotations

import copy
import re

from pain001.corpus.builder import build
from pain001.corpus.registry import load_scenarios, scenario_from
from pain001.corpus.rules.ladder import applicable_overlays, run_ladder
from pain001.corpus.rules.overlays import Overlay, Rule

SCENARIO = next(
    s for s in load_scenarios() if s.id == "gb.chaps.property-purchase"
)
VERSION = "pain.001.001.09"
#: Six cash-account blocks with neither Id nor Prxy: six MDR findings.
ACCOUNTS = "<XAcct><Ccy>EUR</Ccy></XAcct>" * 6


def _overlay(
    overlay_id: str,
    rules: tuple[Rule, ...] = (),
    applies_to: tuple[str, ...] = (),
    versions: tuple[str, ...] = (),
) -> Overlay:
    """An overlay built in the test, applying to every scenario by default."""
    return Overlay(
        overlay_id,
        overlay_id,
        applies_to=applies_to,
        rules=rules,
        versions=versions,
    )


def _broken() -> str:
    """The CHAPS file with nine XSD errors and six MDR findings."""
    xml = build(SCENARIO, VERSION).xml
    xml = re.sub(r"<Nm>[^<]*</Nm>", "<Nm></Nm>", xml)
    xml = re.sub(r"<TwnNm>[^<]*</TwnNm>", "<TwnNm></TwnNm>", xml)
    xml = re.sub(r"<Ctry>[^<]*</Ctry>", "<Ctry>gb</Ctry>", xml)
    return xml.replace("</CdtTrfTxInf>", ACCOUNTS + "</CdtTrfTxInf>")


def test_record_keeps_five_findings_and_counts_apart() -> None:
    """XSD stops at five; MDR and overlays count all, quote five."""
    rules = (
        Rule("no-ccy", "No account currency.", "XAcct/Ccy", "forbidden"),
        Rule("eur", "Say EUR.", "XAcct/Ccy", "equals:GBP", "W1", "warning"),
    )
    pool = [_overlay("t.many", rules)]
    record = run_ladder(SCENARIO, VERSION, _broken(), pool)
    assert record["xsd"]["errors"] == 5
    assert len(record["xsd"]["findings"]) == 5
    assert record["mdr"]["errors"] == 6
    assert (
        record["mdr"]["findings"]
        == [
            "IdentificationOrProxyPresenceRule at "
            "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/XAcct"
        ]
        * 5
    )
    assert record["overlays"] == {
        "t.many": {
            "errors": 6,
            "warnings": 6,
            "findings": ["no-ccy: No account currency."] * 5,
        }
    }


def test_profile_errors_are_not_counted_as_warnings() -> None:
    """A profile error raises the error count only."""
    xml = build(SCENARIO, VERSION).xml.replace('Ccy="GBP"', 'Ccy="USD"')
    profile = run_ladder(SCENARIO, VERSION, xml, [])["profiles"]["uk-chaps"]
    assert profile["errors"] >= 1
    assert profile["warnings"] == 0


def test_overlays_are_chosen_by_edition_family_and_list() -> None:
    """Edition, family and an explicit list each decide; order is kept."""
    pool = [
        _overlay("t.old", versions=("pain.001.001.03",)),
        _overlay("t.other", applies_to=("other-family",)),
        _overlay("t.family", applies_to=(SCENARIO.family,)),
        _overlay("t.every"),
    ]
    chosen = applicable_overlays(SCENARIO, pool, None, VERSION)
    assert [o.overlay_id for o in chosen] == ["t.family", "t.every"]
    xml = build(SCENARIO, VERSION).xml
    record = run_ladder(SCENARIO, VERSION, xml, pool)
    assert list(record["overlays"]) == ["t.family", "t.every"]
    assert [o.overlay_id for o in applicable_overlays(SCENARIO, pool)] == [
        "t.old",
        "t.family",
        "t.every",
    ]
    doc = copy.deepcopy(SCENARIO.data)
    doc["overlays"] = ["t.every"]
    listed = applicable_overlays(scenario_from(doc), pool, None, VERSION)
    assert [o.overlay_id for o in listed] == ["t.every"]


def test_a_patching_overlay_judges_only_its_own_variant() -> None:
    """The generic file skips a patching overlay but keeps the ones after."""
    patched = Overlay("t.patch", "t.patch", patch={"charge_bearer": "SHAR"})
    pool = [patched, _overlay("t.every")]
    generic = applicable_overlays(SCENARIO, pool, None, VERSION)
    assert [o.overlay_id for o in generic] == ["t.every"]
    variant = applicable_overlays(SCENARIO, pool, "t.patch", VERSION)
    assert [o.overlay_id for o in variant] == ["t.patch", "t.every"]
