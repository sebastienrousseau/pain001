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

"""The generated schema coverage sets (ADR-0003, decision 2, WS3).

Acceptance from the plan: thirteen sets, every file schema-valid, 100 %
element-path and choice-branch coverage, checked in CI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.corpus import coverage_sets as cov
from pain001.corpus.inventory import ElementEntry, coverage, inventory_for
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402

COVERAGE_ROOT = build_corpus.COVERAGE_ROOT


def _entry(**kw) -> ElementEntry:
    base = {"path": "/D/X", "kind": "simple"}
    base.update(kw)
    return ElementEntry(**base)


def test_sample_values_follow_the_facets() -> None:
    """Enumeration first, then pattern, then primitive, then length."""
    assert (
        cov.sample_value(_entry(facets={"enumeration": ["SLEV", "SHAR"]}))
        == "SLEV"
    )
    assert (
        cov.sample_value(
            _entry(primitive="decimal", facets={"fraction_digits": 5})
        )
        == "1.00"
    )
    assert (
        cov.sample_value(
            _entry(primitive="decimal", facets={"fraction_digits": 0})
        )
        == "1"
    )
    assert cov.sample_value(_entry(primitive="decimal")) == "1.00"
    for primitive, value in cov.PRIMITIVE_SAMPLES.items():
        assert cov.sample_value(_entry(primitive=primitive)) == value
    assert (
        cov.sample_value(
            _entry(
                primitive="string", facets={"min_length": 1, "max_length": 35}
            )
        )
        == "T"
    )
    assert (
        cov.sample_value(_entry(primitive="string", facets={"min_length": 6}))
        == "TextTe"
    )
    assert cov.sample_value(_entry(primitive="string")) == "T"
    with pytest.raises(cov.CoverageBuildError, match="no sample for pattern"):
        cov.sample_value(_entry(facets={"patterns": ["[0-9]{99}"]}))


def test_every_pattern_sample_matches_its_pattern() -> None:
    """The table is verified, and it covers every pattern the schemas use."""
    for pattern, sample in cov.PATTERN_SAMPLES.items():
        assert re.fullmatch(pattern, sample), pattern
    used = {
        p
        for v in valid_xml_types
        for e in inventory_for(v).elements
        for p in e.facets.get("patterns", [])
    }
    assert used <= set(cov.PATTERN_SAMPLES)


@pytest.mark.parametrize("version", valid_xml_types)
def test_committed_set_is_complete_valid_and_fresh(version: str) -> None:
    """Each edition's set: complete, schema-valid, equal to a rebuild."""
    generated = cov.build_coverage_set(version)
    assert generated.report.complete
    assert generated.report.path_percent == 100.0
    assert generated.report.branch_percent == 100.0
    set_dir = COVERAGE_ROOT / version
    files = sorted(set_dir.glob("*.xml"))
    assert [f.read_text(encoding="utf-8") for f in files] == list(
        generated.files
    )
    xsd = str(DEFAULT_TEMPLATE_REGISTRY.get_template(version).xsd_path)
    for text in generated.files:
        assert validate_xml_string_via_xsd(text, xsd)
    report = json.loads(
        (set_dir / "coverage.json").read_text(encoding="utf-8")
    )
    assert report == build_corpus.slim_report(
        generated.report, generated.manifest
    )
    assert [info.name for info in generated.manifest] == [
        f.name for f in files
    ]
    assert report["complete"] and report["paths"]["percent"] == 100.0
    assert report["sources"] == [f.name for f in files]
    assert coverage(inventory_for(version), files).complete


def test_first_file_is_full_and_later_files_shrink() -> None:
    """File one carries everything the transfer recipe allows; the rest less."""
    generated = cov.build_coverage_set("pain.001.001.09")
    sizes = [len(f) for f in generated.files]
    assert 8 <= len(sizes) <= 16
    assert sizes[0] == max(sizes) and sizes[1] < sizes[0]
    first = generated.files[0]
    assert "<Data>x</Data>" in first  # the xs:any slot is filled
    assert "<PmtMtd>TRF</PmtMtd>" in first and "<ChqInstr>" not in first
    assert "<OrgId>" in first and "<PrvtId>" not in first
    assert "<PrvtId>" in "".join(generated.files[1:])
    # the nested branch under the second branch of an outer choice is reached
    joined = "".join(generated.files)
    assert re.search(r"<PrvtId>.*?<SchmeNm>\s*<Prtry>", joined, re.S)
    assert (
        coverage(inventory_for("pain.001.001.09"), [first]).path_percent > 60
    )


def test_sets_follow_the_mdr_recipes() -> None:
    """Placement is exclusive, the cheque path is its own file, all MDR-clean."""
    from pain001.corpus.rules.mdr import evaluate_mdr

    generated = cov.build_coverage_set("pain.001.001.09")
    for text in generated.files:
        assert evaluate_mdr(text) == []
    cheque_files = [f for f in generated.files if "<PmtMtd>CHK</PmtMtd>" in f]
    assert len(cheque_files) >= 2
    assert all(
        "<ChqInstr>" in f and "<CdtrAcct>" not in f for f in cheque_files
    )
    assert any("<Cd>MLFA</Cd>" in f and "<CdtrAgt>" in f for f in cheque_files)
    assert any(
        "<DlvryMtd>" in f
        and "<Prtry>" in f.split("<DlvryMtd>")[1][:60]
        and "<CdtrAgt>" not in f
        for f in cheque_files
    )
    first = generated.files[0]
    pmtinf_level = first.split("<CdtTrfTxInf>")[0]
    assert "<PmtTpInf>" in pmtinf_level and "<ChrgBr>" in pmtinf_level
    assert "<PmtTpInf>" not in first.split("<CdtTrfTxInf>")[1]
    debit = cov.build_coverage_set("pain.008.001.08")
    for text in debit.files:
        assert evaluate_mdr(text) == []
    assert any("<AmdmntInfDtls>" in f for f in debit.files)
    for f in debit.files:  # when the flag is present it follows the details
        if "<AmdmntInd>" in f:
            assert ("<AmdmntInd>true</AmdmntInd>" in f) == (
                "<AmdmntInfDtls>" in f
            )


def test_file_cap_stops_early_and_reports_incomplete() -> None:
    """max_files bounds the loop; the report says what is left."""
    capped = cov.build_coverage_set("pain.001.001.03", max_files=1)
    assert len(capped.files) == 1 and not capped.report.complete
    assert capped.report.missing_branches


def test_ancestors_and_pattern_free_leaf() -> None:
    """Helper semantics."""
    assert cov._ancestors("/Document/A/B") == {"/Document", "/Document/A"}
    assert cov._ancestors("/Document") == set()


def test_invalid_generated_file_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sample that breaks the schema surfaces as CoverageBuildError."""
    monkeypatch.setitem(cov.PATTERN_SAMPLES, r"[A-Z]{3,3}", "EURO")
    with pytest.raises(cov.CoverageBuildError, match="not schema-valid"):
        cov.build_coverage_set("pain.001.001.03")


def test_strict_gate_passes_on_the_tree(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """make corpus-coverage --strict is green with the committed sets."""
    import corpus_coverage

    assert corpus_coverage.main(["--strict"]) == 0
    out = capsys.readouterr().out
    assert (
        out.count("complete") == len(valid_xml_types) and "no set" not in out
    )


def test_generation_stops_when_a_file_adds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If branch picking cannot progress, the loop ends instead of spinning."""
    monkeypatch.setattr(cov._Planner, "pick_branches", lambda self, unhit: {})
    stalled = cov.build_coverage_set("pain.001.001.03", max_files=6)
    # recipes and exclusive sides still add a few files; branches never do
    assert 1 <= len(stalled.files) <= 6
    assert not stalled.report.complete


def test_planner_with_two_choices_at_one_path(tmp_path: Path) -> None:
    """A child that belongs to one choice is unaffected by the other."""
    from pain001.corpus.inventory import build_inventory

    xsd = tmp_path / "two.xsd"
    xsd.write_text(
        """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
  targetNamespace="urn:two" xmlns="urn:two" elementFormDefault="qualified">
  <xs:element name="Document">
    <xs:complexType><xs:sequence>
      <xs:choice><xs:element name="A" type="xs:string"/><xs:element name="B" type="xs:string"/></xs:choice>
      <xs:choice><xs:element name="C" type="xs:string"/><xs:element name="D" type="xs:string"/></xs:choice>
    </xs:sequence></xs:complexType>
  </xs:element>
</xs:schema>
""",
        encoding="utf-8",
    )
    planner = cov._Planner(build_inventory(xsd, "two"))
    first = planner.emit("/Document", planner.pick_branches(None), None)
    assert list(first) == ["A", "C"]
    picks = planner.pick_branches({"/Document -> B", "/Document/D"})
    second = planner.emit(
        "/Document", picks, {"/Document -> B", "/Document/D"}
    )
    assert list(second) == ["B", "D"]


def test_mdr_breach_in_a_generated_file_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recipe that produced an MDR-invalid file is a build error."""
    from pain001.corpus.rules.mdr import MdrFinding

    monkeypatch.setattr(
        cov, "evaluate_mdr", lambda xml: [MdrFinding("X", "/Document", "boom")]
    )
    with pytest.raises(cov.CoverageBuildError, match="breaks X at /Document"):
        cov.build_coverage_set("pain.001.001.03")


def test_manifest_names_and_describes_every_file() -> None:
    """File names carry their position, recipe and focus; descriptions differ.

    The first file is the baseline that carries every element; every
    later file names the blocks its new coverage falls under, so a
    reader can pick a file without opening it.
    """
    generated = cov.build_coverage_set("pain.001.001.03")
    names = [info.name for info in generated.manifest]
    assert len(names) == len(generated.files) == len(set(names))
    assert names[0] == "01-transfer-every-element.xml"
    assert "every element of the schema" in generated.manifest[0].description
    for index, info in enumerate(generated.manifest, start=1):
        assert info.name.startswith(f"{index:02d}-{info.recipe}-")
        assert info.name.endswith(".xml")
        assert info.adds_paths + info.adds_branches > 0
        assert info.recipe in cov.RECIPE_LABELS
    later = generated.manifest[1]
    assert later.focus and all(block in later.name for block in later.focus)
    assert f"{later.adds_paths} element path" in later.description
    assert {info.recipe for info in generated.manifest} >= {
        "transfer",
        "cheque-to-agent",
        "cheque-no-agent",
    }


def test_describe_file_without_focus_falls_back() -> None:
    """A later file whose hits have no block name is still named."""
    info = cov.describe_file(3, cov.RECIPES["pain.008"][0], 2, 1, ())
    assert info.name == "03-collection-remaining.xml"
    assert "the remaining blocks" in info.description
    assert cov._focus(set(), "/Document/X") == ()
    single = cov._focus(
        {"/D/R/PmtInf/UltmtDbtr/Id/OrgId", "/D/R/PmtInf/UltmtDbtr/Nm -> A+B"},
        "/D/R",
    )
    assert single == ("UltmtDbtr", "Id", "Nm")
