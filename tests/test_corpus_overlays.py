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

"""The overlay assertion grammar shared with the bank-profile MCP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pain001.corpus.builder import build
from pain001.corpus.registry import load_scenarios
from pain001.corpus.rules import overlays as ov

DOC = """<Document xmlns="urn:x"><CstmrCdtTrfInitn><PmtInf>
<ChrgBr>SLEV</ChrgBr>
<Dbtr><PstlAdr><TwnNm>Berlin</TwnNm><AdrLine>Long line</AdrLine></PstlAdr></Dbtr>
<CdtTrfTxInf><Amt><InstdAmt Ccy="EUR">1.00</InstdAmt></Amt>
<Cdtr><Nm>Café</Nm><PstlAdr><Ctry>DE</Ctry></PstlAdr></Cdtr>
<Purp><Cd>SALA</Cd></Purp><RmtInf><Ustrd>Gehalt</Ustrd><Ustrd>Été ☃</Ustrd></RmtInf>
</CdtTrfTxInf></PmtInf></CstmrCdtTrfInitn></Document>"""


def _rule(rule_id: str, locator: str, assertion: str, **extra) -> ov.Rule:
    return ov.parse_rule(
        {
            "rule_id": rule_id,
            "description": rule_id,
            "locator": locator,
            "assertion": assertion,
            **extra,
        }
    )


def _codes(*rules: ov.Rule) -> list[str]:
    return [f.rule_id for f in ov.evaluate_rules(rules, DOC)]


def test_original_three_verbs_read_the_same() -> None:
    """required, equals and if:…:equals behave as the bank-profile engine."""
    assert _codes(_rule("r1", "ChrgBr", "required")) == []
    assert _codes(_rule("r2", "UltmtDbtr", "required")) == ["r2"]
    assert _codes(_rule("r3", "ChrgBr", "equals:SLEV")) == []
    assert _codes(_rule("r4", "ChrgBr", "equals:SHAR")) == ["r4"]
    assert _codes(_rule("r5", "ChrgBr", "if:Ccy=EUR:equals:SLEV")) == []
    assert _codes(_rule("r6", "ChrgBr", "if:Ccy=EUR:equals:SHAR")) == ["r6"]
    assert (
        _codes(_rule("r7", "ChrgBr", "if:Ccy=GBP:equals:SHAR")) == []
    )  # condition not met
    finding = ov.evaluate_rules(
        [
            _rule(
                "r4",
                "ChrgBr",
                "equals:SHAR",
                error_code="X1",
                severity="warning",
            )
        ],
        DOC,
    )[0]
    assert (finding.code, finding.severity, finding.value, finding.path) == (
        "X1",
        "warning",
        "SLEV",
        "/Document/CstmrCdtTrfInitn/PmtInf/ChrgBr",
    )


def test_extended_verbs() -> None:
    """forbidden, one_of, max_length, matches, charset, and if with any tail."""
    assert _codes(_rule("f", "Purp", "forbidden")) == ["f"]
    assert _codes(_rule("f2", "UltmtCdtr", "forbidden")) == []
    assert _codes(_rule("o", "Cd", "one_of:[SALA, SUPP]")) == []
    assert _codes(_rule("o2", "Cd", "one_of:HLST|SUPP")) == ["o2"]
    assert _codes(_rule("m", "AdrLine", "max_length:9")) == []
    assert _codes(_rule("m2", "AdrLine", "max_length:8")) == ["m2"]
    assert _codes(_rule("x", "Ctry", "matches:[A-Z]{2}")) == []
    assert _codes(_rule("x2", "TwnNm", "matches:[a-z]+")) == ["x2"]
    assert _codes(_rule("c", "Nm", "charset:iso20022")) == [
        "c"
    ]  # é is in the Latin set
    assert _codes(_rule("c2", "Nm", "charset:ascii")) == ["c2"]
    assert _codes(_rule("c3", "Ustrd", "charset:latin1")) == [
        "c3"
    ]  # the snowman
    assert _codes(_rule("c4", "Ustrd", "charset:iso20022")) == ["c4"]
    assert _codes(_rule("i", "Purp/Cd", "if:Ccy=EUR:one_of:[SALA]")) == []
    assert _codes(_rule("i2", "UltmtDbtr", "if:Ccy=EUR:required")) == ["i2"]
    assert _codes(_rule("i3", "Purp", "if:Ccy=EUR:forbidden")) == ["i3"]
    # presence form: the tail applies when the element exists at all
    assert _codes(_rule("p1", "TwnNm", "if:PstlAdr:required")) == []
    assert _codes(_rule("p2", "PstCd", "if:PstlAdr:required")) == ["p2"]
    assert _codes(_rule("p3", "PstCd", "if:Nope:required")) == []
    # a condition on something absent never applies; attributes are
    # searched only after elements, and by local name
    assert _codes(_rule("i4", "Purp", "if:Nope=1:forbidden")) == []
    assert (
        _codes(_rule("i5", "Purp", "if:CdtTrfTxInf/Ccy=EUR:forbidden")) == []
    )
    twice = DOC.replace(
        "<TwnNm>Berlin</TwnNm>", "<TwnNm/><TwnNm>Berlin</TwnNm>"
    )
    assert ov.evaluate_rules(
        [_rule("i6", "Purp", "if:TwnNm=Berlin:forbidden")], twice
    )


def test_locators_by_name_and_by_path_suffix() -> None:
    """A path suffix narrows the match; every occurrence is checked."""
    assert _codes(_rule("p", "Cdtr/PstlAdr/TwnNm", "required")) == ["p"]
    assert _codes(_rule("p2", "Dbtr/PstlAdr/TwnNm", "required")) == []
    assert (
        _codes(
            _rule(
                "p3", "/Document/CstmrCdtTrfInitn/PmtInf/ChrgBr", "equals:SLEV"
            )
        )
        == []
    )
    findings = ov.evaluate_rules([_rule("u", "Ustrd", "charset:ascii")], DOC)
    assert [f.path for f in findings] == [
        "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/RmtInf/Ustrd"
    ]
    assert findings[0].value == "Été ☃"
    # an element present but empty does not satisfy required
    empty = DOC.replace("<TwnNm>Berlin</TwnNm>", "<TwnNm/>")
    assert [
        f.rule_id
        for f in ov.evaluate_rules([_rule("e", "TwnNm", "required")], empty)
    ] == ["e"]
    assert [
        f.rule_id
        for f in ov.evaluate_rules(
            [_rule("e2", "TwnNm", "equals:Berlin")], empty
        )
    ] == ["e2"]
    assert [
        f.rule_id
        for f in ov.evaluate_rules(
            [_rule("e3", "TwnNm", "max_length:5")], empty
        )
    ] == []


def test_parse_rule_and_assertion_errors() -> None:
    """Every malformed shape is named."""
    with pytest.raises(ov.OverlayError, match="missing description, locator"):
        ov.parse_rule({"rule_id": "r", "assertion": "required"})
    with pytest.raises(ov.OverlayError, match="unknown verb"):
        ov.parse_rule(
            {
                "rule_id": "r",
                "description": "d",
                "locator": "X",
                "assertion": "exists",
            }
        )
    for bad, message in [
        ("one_of:[]", "at least one value"),
        ("max_length:many", "needs a number"),
        ("matches:[", "bad regex"),
        ("charset:klingon", "charset must be one of"),
        ("if::equals:X", "form if:"),
        ("if:Ccy=EUR", "form if:"),
        ("if:Ccy=EUR:if:X=Y:required", "cannot nest"),
    ]:
        with pytest.raises(ov.OverlayError, match=message):
            ov.parse_rule(
                {
                    "rule_id": "r",
                    "description": "d",
                    "locator": "X",
                    "assertion": bad,
                }
            )
    with pytest.raises(ov.OverlayError, match="severity must be"):
        ov.parse_rule(
            {
                "rule_id": "r",
                "description": "d",
                "locator": "X",
                "assertion": "required",
                "severity": "fatal",
            }
        )
    assert ov.assertion_is_known(
        "if:A=B:equals:C"
    ) and not ov.assertion_is_known("exists")
    assert _rule("r", "X", "required").code == "r"


def test_overlay_files_in_both_shapes(tmp_path: Path) -> None:
    """Corpus YAML and bank-profile JSON both load; errors carry the path."""
    profile = {
        "profile_id": "SEPA_Instant",
        "market_practice": "SEPA SCT Inst",
        "supported_messages": ["pain.001"],
        "custom_rules": [
            {
                "rule_id": "sepa-eur-slev",
                "description": "d",
                "locator": "ChrgBr",
                "assertion": "if:Ccy=EUR:equals:SLEV",
                "error_code": "SEPA_CHRGBR_NOT_SLEV",
                "severity": "error",
            }
        ],
    }
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    json_file = good_dir / "sepa_instant.json"
    json_file.write_text(json.dumps(profile), encoding="utf-8")
    loaded = ov.load_overlay(json_file)
    assert (
        loaded.overlay_id == "SEPA_Instant" and loaded.title == "SEPA SCT Inst"
    )
    assert (
        loaded.rules[0].code == "SEPA_CHRGBR_NOT_SLEV"
        and loaded.path == json_file
    )
    assert loaded.applies("anything") and ov.evaluate(loaded, DOC) == []
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "bad.yaml").write_text("overlay_id: [", encoding="utf-8")
    with pytest.raises(ov.OverlayError, match="not valid YAML"):
        ov.load_overlay(bad_dir / "bad.yaml")
    (bad_dir / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(ov.OverlayError, match="not valid JSON"):
        ov.load_overlay(bad_dir / "bad.json")
    (bad_dir / "list.yaml").write_text("- 1\n", encoding="utf-8")
    with pytest.raises(ov.OverlayError, match="mapping at the top level"):
        ov.load_overlay(bad_dir / "list.yaml")
    with pytest.raises(ov.OverlayError, match="overlay_id .* is required"):
        ov.overlay_from({"rules": []})
    with pytest.raises(ov.OverlayError, match="duplicate rule ids"):
        ov.overlay_from(
            {
                "overlay_id": "x",
                "rules": [
                    {
                        "rule_id": "a",
                        "description": "d",
                        "locator": "X",
                        "assertion": "required",
                    }
                ]
                * 2,
            }
        )
    single = ov.overlay_from(
        {"overlay_id": "x", "applies_to": "sepa-credit-transfer"}
    )
    patched = ov.overlay_from(
        {
            "overlay_id": "y",
            "patch": {"payment": {"type": {"service_level": "URNS"}}},
        }
    )
    assert patched.patch == {"payment": {"type": {"service_level": "URNS"}}}
    assert single.patch == {}
    assert single.applies_to == ("sepa-credit-transfer",)
    assert single.applies(
        "de.x", "sepa-credit-transfer"
    ) and not single.applies("de.x", "other")
    assert ov.load_overlays(tmp_path / "none") == []
    assert [o.overlay_id for o in ov.load_overlays(good_dir)] == [
        "SEPA_Instant"
    ]


def test_shipped_overlay_against_the_chaps_scenario() -> None:
    """The BoE overlay passes on the CHAPS files and flags a stripped one."""
    overlays = ov.load_overlays()
    assert "gb.boe.chaps-enhanced-data" in [o.overlay_id for o in overlays]
    overlay = next(
        o for o in overlays if o.overlay_id == "gb.boe.chaps-enhanced-data"
    )
    assert overlay.applies("gb.chaps.property-purchase", "priority-payment")
    assert not overlay.applies("de.sepa.sct-salary", "sepa-credit-transfer")
    scenario = {s.id: s for s in load_scenarios()}[
        "gb.chaps.property-purchase"
    ]
    for version in scenario.versions:
        assert ov.evaluate(overlay, build(scenario, version).xml) == []
    stripped = (
        build(scenario, "pain.001.001.09")
        .xml.replace("<Cd>HLST</Cd>", "<Cd>SUPP</Cd>")
        .replace("<ChrgBr>SHAR</ChrgBr>", "<ChrgBr>SLEV</ChrgBr>")
    )
    findings = ov.evaluate(overlay, stripped)
    assert [f.code for f in findings] == [
        "CHAPS_PURPOSE_NOT_PROPERTY",
        "CHAPS_CHRGBR_NOT_SHAR",
    ]
    assert (
        findings[0].severity == "warning" and findings[1].severity == "error"
    )
