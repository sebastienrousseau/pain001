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

"""The schema inventory and the coverage yardstick (ADR-0003, WS1).

Pinned on pain.001.001.03, .09, .13 and pain.008.001.02, the four
shapes the plan names, plus the gate script's pass and fail paths.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.corpus import (
    ChoiceEntry,
    ElementEntry,
    Inventory,
    build_inventory,
    coverage,
    inventory_for,
    present_paths,
)
from pain001.corpus import inventory as inventory_module
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import corpus_coverage  # noqa: E402

CCT = "/Document/CstmrCdtTrfInitn"
DD = "/Document/CstmrDrctDbtInitn"


def _by_path(message_type: str) -> dict[str, ElementEntry]:
    return {e.path: e for e in inventory_for(message_type).elements}


@pytest.mark.parametrize(
    ("message_type", "min_entries", "min_choices"),
    [
        ("pain.001.001.03", 900, 70),
        ("pain.001.001.09", 1500, 120),
        ("pain.001.001.13", 1600, 125),
        ("pain.008.001.02", 1000, 80),
    ],
)
def test_inventory_size_and_uniqueness(
    message_type: str, min_entries: int, min_choices: int
) -> None:
    """Every path is unique and the walk reaches the whole schema."""
    inv = inventory_for(message_type)
    assert inv.message_type == message_type
    assert inv.namespace.endswith(message_type)
    assert len(inv.elements) >= min_entries
    assert len(inv.choices) >= min_choices
    assert len(inv.paths()) == len(inv.elements)
    assert inv.elements[0].path == "/Document"


def test_inventory_for_is_cached_and_rejects_unknown_types() -> None:
    """Two calls share one object; a foreign name raises KeyError."""
    assert inventory_for("pain.001.001.03") is inventory_for("pain.001.001.03")
    with pytest.raises(KeyError):
        inventory_for("pain.001.001.99")


def test_leaf_facets_and_occurrences() -> None:
    """Facets, primitives, attributes and cardinalities are captured."""
    e = _by_path("pain.001.001.09")
    amount = e[f"{CCT}/PmtInf/CdtTrfTxInf/Amt/InstdAmt"]
    assert amount.kind == "simple"
    assert amount.type_name == "ActiveOrHistoricCurrencyAndAmount"
    assert amount.primitive == "decimal"
    assert amount.facets["fraction_digits"] == 5
    assert amount.facets["total_digits"] == 18
    assert amount.facets["min_inclusive"] == "0"
    ccy = e[f"{CCT}/PmtInf/CdtTrfTxInf/Amt/InstdAmt/@Ccy"]
    assert ccy.kind == "attribute"
    assert ccy.min_occurs == 1  # use="required"
    assert ccy.facets["patterns"] == ["[A-Z]{3,3}"]
    assert e[f"{CCT}/GrpHdr/MsgId"].facets == {
        "min_length": 1,
        "max_length": 35,
    }
    assert e[f"{CCT}/PmtInf/ChrgBr"].facets["enumeration"] == [
        "DEBT",
        "CRED",
        "SHAR",
        "SLEV",
    ]
    assert e[f"{CCT}/PmtInf"].max_occurs is None  # unbounded
    assert e[f"{CCT}/PmtInf"].min_occurs == 1
    assert e[f"{CCT}/GrpHdr/Authstn"].min_occurs == 0
    assert e[f"{CCT}/GrpHdr/Authstn"].max_occurs == 2
    assert e[f"{CCT}/GrpHdr"].kind == "complex"
    assert e[f"{CCT}/GrpHdr"].type_name == "GroupHeader85"


def test_choices_and_any_slots() -> None:
    """Choice branches and xs:any slots are listed where they sit."""
    inv = inventory_for("pain.001.001.09")
    choices = {c.path: c for c in inv.choices}
    assert choices[f"{CCT}/GrpHdr/Authstn"].branches == (("Cd",), ("Prtry",))
    assert choices[f"{CCT}/GrpHdr/Authstn"].branch_ids() == [
        f"{CCT}/GrpHdr/Authstn -> Cd",
        f"{CCT}/GrpHdr/Authstn -> Prtry",
    ]
    assert choices[f"{CCT}/GrpHdr/InitgPty/Id"].branches == (
        ("OrgId",),
        ("PrvtId",),
    )
    anys = [e for e in inv.elements if e.kind == "any"]
    assert {a.path for a in anys} == {
        f"{CCT}/SplmtryData/Envlp/*",
        f"{CCT}/PmtInf/CdtTrfTxInf/SplmtryData/Envlp/*",
    }


def test_v03_has_no_any_slot_and_v13_adds_uetr() -> None:
    """The inventory reflects what each edition added."""
    assert not [
        e for e in inventory_for("pain.001.001.03").elements if e.kind == "any"
    ]
    v13 = _by_path("pain.001.001.13")
    assert f"{CCT}/PmtInf/CdtTrfTxInf/PmtId/UETR" in v13
    assert f"{CCT}/PmtInf/CdtTrfTxInf/PmtId/UETR" not in _by_path(
        "pain.001.001.03"
    )


def test_direct_debit_inventory_has_mandate_paths() -> None:
    """pain.008 walks to the mandate block."""
    e = _by_path("pain.008.001.02")
    assert f"{DD}/PmtInf/DrctDbtTxInf/DrctDbtTx/MndtRltdInf/MndtId" in e
    assert e[f"{DD}/PmtInf/PmtTpInf/SeqTp"].facets["enumeration"] == [
        "FRST",
        "RCUR",
        "FNAL",
        "OOFF",
    ]


def test_dict_and_json_round_trip() -> None:
    """to_dict/from_dict and to_json preserve the inventory exactly."""
    inv = inventory_for("pain.008.001.02")
    assert Inventory.from_dict(inv.to_dict()) == inv
    assert Inventory.from_dict(json.loads(inv.to_json())) == inv
    assert Inventory.from_dict(json.loads(inv.to_json(indent=None))) == inv


def test_build_inventory_from_a_path(tmp_path: Path) -> None:
    """A schema anywhere on disk can be inventoried under any label."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    copy = tmp_path / "x.xsd"
    copy.write_bytes(meta.xsd_path.read_bytes())
    inv = build_inventory(copy, "custom")
    assert inv.message_type == "custom"
    assert inv.paths() == inventory_for("pain.001.001.03").paths()


def test_recursion_guard_stops_a_self_referencing_type(tmp_path: Path) -> None:
    """A type that contains itself is recorded once, not forever."""
    xsd = tmp_path / "loop.xsd"
    xsd.write_text(
        """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
  targetNamespace="urn:loop" xmlns="urn:loop" elementFormDefault="qualified">
  <xs:element name="Document" type="Node"/>
  <xs:complexType name="Node">
    <xs:sequence>
      <xs:element name="Child" type="Node" minOccurs="0"/>
      <xs:element name="Leaf" type="xs:string" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )
    inv = build_inventory(xsd, "loop")
    assert inv.paths() == {"/Document", "/Document/Child", "/Document/Leaf"}


def test_depth_cap_stops_a_deep_but_non_recursive_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MAX_DEPTH bounds descent even when every type is distinct."""
    types = "".join(
        f'<xs:complexType name="T{i}"><xs:sequence>'
        f'<xs:element name="L{i}" type="T{i + 1}"/>'
        "</xs:sequence></xs:complexType>"
        for i in range(6)
    )
    xsd = tmp_path / "deep.xsd"
    xsd.write_text(
        '<?xml version="1.0"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'targetNamespace="urn:deep" xmlns="urn:deep" elementFormDefault="qualified">'
        '<xs:element name="Document" type="T0"/>'
        + types
        + '<xs:complexType name="T6"><xs:sequence>'
        '<xs:element name="End" type="xs:string"/></xs:sequence></xs:complexType>'
        "</xs:schema>",
        encoding="utf-8",
    )
    assert (
        "/Document/L0/L1/L2/L3/L4/L5/End"
        in build_inventory(xsd, "deep").paths()
    )
    monkeypatch.setattr(inventory_module, "MAX_DEPTH", 3)
    capped = build_inventory(xsd, "deep").paths()
    assert "/Document/L0/L1/L2" in capped
    assert "/Document/L0/L1/L2/L3" not in capped


def test_present_paths_from_text_and_file(tmp_path: Path) -> None:
    """Namespaces are stripped, attributes kept, xsi attributes dropped."""
    text = (
        '<Document xmlns="urn:x" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xsi:schemaLocation="urn:x x.xsd"><A><B Ccy="EUR">1</B></A></Document>'
    )
    expected = {
        "/Document",
        "/Document/A",
        "/Document/A/B",
        "/Document/A/B/@Ccy",
    }
    assert present_paths(text) == expected
    f = tmp_path / "d.xml"
    f.write_text(text, encoding="utf-8")
    assert present_paths(f) == expected
    assert present_paths(str(f)) == expected


def test_coverage_of_the_bundled_example() -> None:
    """The bundled .03 example hits the basics and misses the rest."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    report = coverage(
        inventory_for("pain.001.001.03"), [meta.example_xml_path]
    )
    assert report.message_type == "pain.001.001.03"
    assert report.sources == (str(meta.example_xml_path),)
    assert f"{CCT}/GrpHdr/MsgId" in report.hit_paths
    assert f"{CCT}/GrpHdr/Authstn" in report.missing_paths
    assert f"{CCT}/GrpHdr/Authstn -> Cd" in report.missing_branches
    assert 0 < report.path_percent < 100
    assert 0 < report.branch_percent < 100
    assert not report.complete
    assert report.unknown == ()
    assert report.to_dict()["complete"] is False


def test_coverage_exemptions_any_slots_and_unknown_paths() -> None:
    """Exempting everything missing completes the gate; any slots count."""
    inv = inventory_for("pain.001.001.09")
    doc = (
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09">'
        "<CstmrCdtTrfInitn><GrpHdr><MsgId>1</MsgId><Authstn><Cd>AUTH</Cd></Authstn>"
        "</GrpHdr><SplmtryData><Envlp><Custom>x</Custom></Envlp></SplmtryData>"
        "<NotInSchema/></CstmrCdtTrfInitn></Document>"
    )
    partial = coverage(inv, [doc])
    assert partial.sources == ("<inline>",)
    assert f"{CCT}/SplmtryData/Envlp/*" in partial.hit_paths
    assert f"{CCT}/GrpHdr/Authstn -> Cd" in partial.hit_branches
    assert f"{CCT}/GrpHdr/Authstn -> Prtry" in partial.missing_branches
    assert partial.unknown == (f"{CCT}/NotInSchema",)
    full = coverage(
        inv, [doc], partial.missing_paths + partial.missing_branches
    )
    assert full.complete
    assert full.path_percent == 100.0 and full.branch_percent == 100.0
    assert full.exempt == tuple(
        sorted(partial.missing_paths + partial.missing_branches)
    )
    empty = coverage(
        inv,
        [],
        inv.paths() | {b for c in inv.choices for b in c.branch_ids()},
    )
    assert empty.complete and empty.path_percent == 100.0


def test_gate_reports_every_version_without_sets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no coverage sets the gate informs and passes; strict fails."""
    out = tmp_path / "report.json"
    assert (
        corpus_coverage.main(
            ["--coverage-root", str(tmp_path), "--json", str(out)]
        )
        == 0
    )
    text = capsys.readouterr().out
    assert text.count("no set") == len(valid_xml_types)
    assert set(json.loads(out.read_text())) == set(valid_xml_types)
    assert (
        corpus_coverage.main(["--coverage-root", str(tmp_path), "--strict"])
        == 1
    )
    assert "fail the coverage gate" in capsys.readouterr().out


def test_gate_fails_on_an_incomplete_set_and_honours_exemptions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real set that misses paths fails; exempting them passes."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    set_dir = tmp_path / "pain.001.001.03"
    set_dir.mkdir()
    (set_dir / "set-01.xml").write_bytes(meta.example_xml_path.read_bytes())
    assert corpus_coverage.main(["--coverage-root", str(tmp_path)]) == 1
    text = capsys.readouterr().out
    assert (
        "INCOMPLETE" in text
        and "missing path" in text
        and "missing branch" in text
    )
    report = coverage(
        inventory_for("pain.001.001.03"), [set_dir / "set-01.xml"]
    )
    (set_dir / "exemptions.txt").write_text(
        "# everything the example does not reach\n"
        + "\n".join(report.missing_paths + report.missing_branches)
        + "\n",
        encoding="utf-8",
    )
    assert (
        corpus_coverage.read_exemptions(set_dir)[0] == report.missing_paths[0]
    )
    assert corpus_coverage.read_exemptions(tmp_path) == []
    assert corpus_coverage.main(["--coverage-root", str(tmp_path)]) == 0
    assert "complete" in capsys.readouterr().out


def test_gate_writes_inventories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--inventory DIR writes one JSON per bundled type."""
    assert corpus_coverage.main(["--inventory", str(tmp_path / "inv")]) == 0
    files = sorted(p.name for p in (tmp_path / "inv").glob("*.json"))
    assert files == sorted(f"{t}.json" for t in valid_xml_types)
    data = json.loads((tmp_path / "inv" / "pain.001.001.03.json").read_text())
    assert Inventory.from_dict(data) == inventory_for("pain.001.001.03")
    assert "pain.008.001.08:" in capsys.readouterr().out


def test_measure_without_example_reports_nothing_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bundle whose example is missing measures as empty, not as an error."""
    from dataclasses import replace

    registry = dict(DEFAULT_TEMPLATE_REGISTRY._registry)
    registry["pain.001.001.03"] = replace(
        registry["pain.001.001.03"], example_xml_path=None
    )
    monkeypatch.setattr(DEFAULT_TEMPLATE_REGISTRY, "_registry", registry)
    report, real = corpus_coverage.measure("pain.001.001.03", tmp_path)
    assert not real and report.hit_paths == () and report.sources == ()


def test_choice_entry_ids_for_sequence_and_any_branches() -> None:
    """Branch ids join multi-element branches with '+'."""
    entry = ChoiceEntry("/D/X", (("A", "B"), ("*",)))
    assert entry.branch_ids() == ["/D/X -> A+B", "/D/X -> *"]
