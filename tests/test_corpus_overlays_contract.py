# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Overlay files, rules and findings: the exact contract.

``test_corpus_overlays.py`` covers the verbs. These pin what a reader
of an error or a finding relies on: where an error says it happened,
the wording of the known-verb and charset lists, which file suffixes
load, and every field a finding carries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pain001.corpus.rules import overlays as ov

DOC = """<Document xmlns="urn:x"><CstmrCdtTrfInitn><PmtInf>
<ChrgBr>SLEV</ChrgBr><Dbtr><Nm>Debtor</Nm></Dbtr>
<CdtTrfTxInf><Amt><InstdAmt Ccy="EUR">1.00</InstdAmt></Amt>
<Cdtr><Nm>Creditor</Nm></Cdtr></CdtTrfTxInf>
</PmtInf></CstmrCdtTrfInitn></Document>"""
RULE = {
    "rule_id": "r1",
    "description": "The charge bearer is SLEV.",
    "locator": "ChrgBr",
    "assertion": "equals:SLEV",
}


def _rule(locator: str, assertion: str, rule_id: str = "r1") -> ov.Rule:
    """A rule built without parsing, as an overlay file would give it."""
    return ov.Rule(rule_id, f"{rule_id} description", locator, assertion)


def test_parse_rule_keeps_every_field() -> None:
    """Description, code and severity survive parsing."""
    rule = ov.parse_rule(dict(RULE, error_code="E1", severity="warning"))
    assert rule == ov.Rule(
        "r1",
        "The charge bearer is SLEV.",
        "ChrgBr",
        "equals:SLEV",
        "E1",
        "warning",
    )


def test_unknown_verb_lists_the_known_ones() -> None:
    """The message names the rule, the assertion and every verb."""
    raw = dict(RULE, assertion="like:SLEV")
    message = (
        "f.yaml: rule 'r1' uses an unknown verb in 'like:SLEV'; known verbs: "
        "required, forbidden, equals:, one_of:, max_length:, matches:, "
        "charset:, if:"
    )
    with pytest.raises(ov.OverlayError) as caught:
        ov.parse_rule(raw, "f.yaml")
    assert str(caught.value) == message


def test_assertion_errors_name_the_rule() -> None:
    """A bad argument, also in an if tail, is reported against the rule."""
    for assertion, tail in (
        ("one_of:[]", "one_of needs at least one value"),
        ("if:Ccy=EUR:one_of:[]", "one_of needs at least one value"),
        ("charset:ebcdic", "charset must be one of iso20022, ascii, latin1"),
    ):
        with pytest.raises(ov.OverlayError) as caught:
            ov.parse_rule(dict(RULE, assertion=assertion), "f.yaml")
        assert str(caught.value) == f"f.yaml: rule 'r1': {tail}"
    with pytest.raises(ov.OverlayError) as caught:
        ov.evaluate_rules([_rule("Nm", "one_of:", "r9")], DOC)
    assert str(caught.value) == "r9: one_of needs at least one value"


def test_a_bare_rule_error_is_labelled_rule() -> None:
    """Without a label, a rule's error starts with <rule>."""
    with pytest.raises(ov.OverlayError) as caught:
        ov.parse_rule({})
    assert str(caught.value) == (
        "<rule>: rule is missing rule_id, description, locator, assertion"
    )


def test_overlay_errors_say_where() -> None:
    """Without a path the label is <overlay>; with one it is the path."""
    with pytest.raises(ov.OverlayError) as caught:
        ov.overlay_from({})
    assert str(caught.value) == (
        "<overlay>: overlay_id (or profile_id) is required"
    )
    path = Path("bank/profile.yaml")
    with pytest.raises(ov.OverlayError) as caught:
        ov.overlay_from({}, path)
    assert str(caught.value) == (
        "bank/profile.yaml: overlay_id (or profile_id) is required"
    )
    bad = {"overlay_id": "o", "rules": [{"rule_id": "r1"}]}
    with pytest.raises(ov.OverlayError) as caught:
        ov.overlay_from(bad)
    assert str(caught.value) == (
        "<overlay>: rule is missing description, locator, assertion"
    )
    with pytest.raises(ov.OverlayError, match=r"^bank/profile\.yaml: rule"):
        ov.overlay_from(bad, path)


def test_overlay_keeps_title_and_source() -> None:
    """The title wins over the market practice; the source is kept."""
    overlay = ov.overlay_from(
        {
            "overlay_id": "o",
            "title": "Title",
            "market_practice": "Practice",
            "source": {"publisher": "Example scheme", "year": 2026},
        }
    )
    assert overlay.title == "Title"
    assert overlay.source == {"publisher": "Example scheme", "year": 2026}
    assert overlay.rules == ()
    assert ov.overlay_from({"profile_id": "p"}).source == {}


def test_json_and_yml_files_load(tmp_path: Path) -> None:
    """``.json`` is read as JSON (its errors say so) and ``.yml`` is found."""
    (tmp_path / "a.yml").write_text("overlay_id: a\n", encoding="utf-8")
    (tmp_path / "b.json").write_text(
        json.dumps({"overlay_id": "b", "versions": [1e3]}), encoding="utf-8"
    )
    (tmp_path / "c.txt").write_text("overlay_id: c\n", encoding="utf-8")
    loaded = ov.load_overlays(tmp_path)
    assert [o.overlay_id for o in loaded] == ["a", "b"]
    assert loaded[1].versions == ("1000.0",), "a JSON number, not YAML text"
    broken = tmp_path / "d.json"
    broken.write_text('{"overlay_id": }', encoding="utf-8")
    with pytest.raises(ov.OverlayError) as caught:
        ov.load_overlay(broken)
    assert str(caught.value).startswith(
        f"{broken}: not valid JSON: Expecting value"
    )


def test_path_locators_ignore_outer_slashes() -> None:
    """A leading or trailing slash on a path locator changes nothing."""
    for locator in ("/ChrgBr", "PmtInf/ChrgBr/", "/PmtInf/ChrgBr"):
        findings = ov.evaluate_rules([_rule(locator, "equals:SHAR")], DOC)
        assert [f.path for f in findings] == [
            "/Document/CstmrCdtTrfInitn/PmtInf/ChrgBr"
        ], locator
    xml = "<Doc><X>1</X></Doc>"
    findings = ov.evaluate_rules([_rule("Doc/X", "equals:2")], xml)
    assert [(f.path, f.value) for f in findings] == [("/Doc/X", "1")]


def test_one_of_strips_brackets_only_when_paired() -> None:
    """``[a|b`` keeps its bracket; ``[a|b]`` loses both."""
    assert ov._parse_assertion("one_of:[SLEV|SHAR", "w") == (
        "one_of",
        ["[SLEV", "SHAR"],
    )
    assert ov._parse_assertion("one_of:SLEV|SHAR]", "w") == (
        "one_of",
        ["SLEV", "SHAR]"],
    )


def test_if_condition_splits_on_the_first_equals() -> None:
    """The condition value may itself contain ``=``."""
    verb, (pair, tail) = ov._parse_assertion("if:Nm=a=b:required", "w")
    assert (verb, pair, tail) == ("if", ("Nm", "a=b"), ("required", None))


def test_latin1_charset_stops_at_255() -> None:
    """U+00FF is Latin-1, U+0100 is not."""
    assert ov._charset_ok("ÿ", "latin1")
    assert not ov._charset_ok("Ā", "latin1")


def test_forbidden_fires_on_a_present_element() -> None:
    """Each present element under a forbidden locator is a finding."""
    findings = ov.evaluate_rules([_rule("Nm", "forbidden")], DOC)
    assert [(f.path, f.value) for f in findings] == [
        ("/Document/CstmrCdtTrfInitn/PmtInf/Dbtr/Nm", "Debtor"),
        (
            "/Document/CstmrCdtTrfInitn/PmtInf/CdtTrfTxInf/Cdtr/Nm",
            "Creditor",
        ),
    ]


def test_an_unmet_condition_skips_only_its_own_rule() -> None:
    """Rules after a skipped conditional rule are still evaluated."""
    rules = [
        _rule("ChrgBr", "if:Ccy=USD:equals:SHAR", "r1"),
        _rule("ChrgBr", "if:Purp:equals:SHAR", "r2"),
        _rule("ChrgBr", "equals:SHAR", "r3"),
    ]
    assert [f.rule_id for f in ov.evaluate_rules(rules, DOC)] == ["r3"]


def test_finding_carries_every_rule_field() -> None:
    """A missing required element is reported at its locator, in full."""
    rule = ov.Rule("r1", "Town is required.", "TwnNm", "required", "E-TWN")
    assert ov.evaluate_rules([rule], DOC) == [
        ov.Finding(
            "r1",
            "E-TWN",
            "error",
            "TwnNm",
            "TwnNm",
            "required",
            "Town is required.",
            None,
        )
    ]
    found = ov.evaluate_rules([_rule("ChrgBr", "matches:SH.*")], DOC)[0]
    assert (found.locator, found.assertion, found.message) == (
        "ChrgBr",
        "matches:SH.*",
        "r1 description",
    )
