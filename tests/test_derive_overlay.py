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

"""The author-side guideline diff: reads outside the repo, writes nothing."""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import pytest

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import derive_overlay  # noqa: E402


def _guideline(tmp_path: Path) -> Path:
    """A synthetic guideline: the .03 XSD with a few restrictions applied.

    Written under the system temp directory, outside the repository, as
    a real guideline export would be.
    """
    base = DEFAULT_TEMPLATE_REGISTRY.get_template(
        "pain.001.001.03"
    ).xsd_path.read_text(encoding="utf-8")
    text = base
    # remove the equivalent-amount branch entirely
    text = re.sub(
        r'<xs:element name="EqvtAmt" type="EquivalentAmount2"/>', "", text
    )
    # make the debtor name mandatory
    text = text.replace(
        '<xs:element maxOccurs="1" minOccurs="0" name="Nm" type="Max140Text"/>',
        '<xs:element maxOccurs="1" minOccurs="1" name="Nm" type="Max140Text"/>',
        1,
    )
    # narrow the service level to one code and shorten the end-to-end id
    text = text.replace(
        '<xs:element name="Cd" type="ExternalServiceLevel1Code"/>',
        '<xs:element name="Cd" type="ServiceLevelUrns"/>',
        1,
    )
    text = text.replace(
        '<xs:simpleType name="Max35Text">',
        """<xs:simpleType name="ServiceLevelUrns">
    <xs:restriction base="xs:string"><xs:enumeration value="URNS"/></xs:restriction>
  </xs:simpleType>
  <xs:simpleType name="Max18TextUg">
    <xs:restriction base="xs:string"><xs:minLength value="1"/><xs:maxLength value="18"/></xs:restriction>
  </xs:simpleType>
  <xs:simpleType name="Max35Text">""",
        1,
    )
    text = text.replace(
        '<xs:element name="EndToEndId" type="Max35Text"/>',
        '<xs:element name="EndToEndId" type="Max18TextUg"/>',
        1,
    )
    assert text != base
    outside = Path(tempfile.mkdtemp(prefix="pain001-guideline-", dir="/tmp"))
    path = outside / "guideline.xsd"
    path.write_text(text, encoding="utf-8")
    return path


def test_diff_reports_each_kind_of_restriction(tmp_path: Path) -> None:
    """Removed, mandatory, narrowed and shortened items are found."""
    changes = derive_overlay.diff(_guideline(tmp_path), "pain.001.001.03")
    assert ("PmtInf/CdtTrfTxInf/Amt/EqvtAmt",) in changes["removed"]
    assert all(
        not p[0].startswith("PmtInf/CdtTrfTxInf/Amt/EqvtAmt/")
        for p in changes["removed"]
    )
    assert any(p.endswith("/Nm") for p, _, _ in changes["mandatory"])
    assert any(values == ["URNS"] for _, values in changes["enum"])
    assert any(
        p.endswith("PmtId/EndToEndId") and new == 18
        for p, _, new in changes["length"]
    )
    assert changes["capped"] == [] and changes["pattern"] == []
    rules = derive_overlay.as_rules(changes)
    assert (
        "- {locator: PmtInf/CdtTrfTxInf/Amt/EqvtAmt, assertion: forbidden}"
        in rules
    )
    assert any(
        "/Nm, assertion: if:" in r and r.endswith(":required}") for r in rules
    )
    assert any("one_of:[URNS]" in r for r in rules)
    assert any("max_length:18" in r for r in rules)


def test_main_prints_and_refuses_paths_inside_the_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The report and the rule form print; an in-repo path is refused."""
    guideline = _guideline(tmp_path)
    assert (
        derive_overlay.main([str(guideline), "--base", "pain.001.001.03"]) == 0
    )
    out = capsys.readouterr().out
    assert "removed (" in out and "PmtInf/CdtTrfTxInf/Amt/EqvtAmt" in out
    assert (
        derive_overlay.main(
            [str(guideline), "--base", "pain.001.001.03", "--as-rules"]
        )
        == 0
    )
    assert "assertion: forbidden" in capsys.readouterr().out
    inside = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03").xsd_path
    assert derive_overlay.main([str(inside), "--base", "pain.001.001.03"]) == 1
    assert "refusing" in capsys.readouterr().out


def test_as_rules_covers_patterns_and_top_level_mandatory() -> None:
    """Pattern changes and a root-level mandatory element render too."""
    rules = derive_overlay.as_rules(
        {
            "removed": [],
            "mandatory": [("GrpHdr", 0, 1)],
            "capped": [],
            "enum": [],
            "length": [],
            "pattern": [("PmtInf/PmtInfId", ["[A-Z]{3}"])],
        }
    )
    assert rules == [
        "- {locator: GrpHdr, assertion: required}",
        "- {locator: PmtInf/PmtInfId, assertion: 'matches:[A-Z]{3}'}",
    ]
