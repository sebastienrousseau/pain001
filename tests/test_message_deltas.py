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

"""``docs/message-deltas.md`` is generated and cannot go stale."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_message_deltas as deltas  # noqa: E402

CCT = "PmtInf/CdtTrfTxInf"


def test_document_is_up_to_date(capsys: pytest.CaptureFixture[str]) -> None:
    """``--check`` passes on a clean tree."""
    assert deltas.main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_reports_a_stale_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing or edited document fails ``--check`` and is not written."""
    target = tmp_path / "message-deltas.md"
    monkeypatch.setattr(deltas, "OUT", target)
    assert deltas.main(["--check"]) == 1
    assert "STALE" in capsys.readouterr().out
    assert not target.exists()
    assert deltas.main([]) == 0
    assert target.exists()
    assert deltas.main([]) == 0  # second run: already up to date


def test_steps_cover_every_consecutive_pair() -> None:
    """Ten pain.001 steps and the pain.008 step, in order."""
    assert deltas.STEPS[0] == ("pain.001.001.03", "pain.001.001.04")
    assert deltas.STEPS[-2] == ("pain.001.001.12", "pain.001.001.13")
    assert deltas.STEPS[-1] == ("pain.008.001.02", "pain.008.001.08")
    assert len(deltas.STEPS) == 11


def test_known_deltas_are_reported() -> None:
    """Spot checks against what the ISO editions are known to have done."""
    d = deltas.compute("pain.001.001.12", "pain.001.001.13")
    added13 = {deltas._relative(e.path) for e in d.added}
    assert f"{CCT}/RgltryRptg/Dtls/RptgCd" in added13
    assert f"{CCT}/RmtInf/Strd/SctiesData" in added13
    uetr = deltas.compute("pain.001.001.08", "pain.001.001.09")
    assert f"{CCT}/PmtId/UETR" in {
        deltas._relative(e.path) for e in uetr.added
    }
    dd = deltas.compute("pain.008.001.02", "pain.008.001.08")
    removed = {deltas._relative(e.path) for e in dd.removed}
    added = {deltas._relative(e.path) for e in dd.added}
    assert "PmtInf/CdtrAgt/FinInstnId/BIC" in removed
    assert "PmtInf/CdtrAgt/FinInstnId/BICFI" in added
    assert dd.branches_added and not dd.branches_removed
    same = deltas.compute("pain.001.001.10", "pain.001.001.11")
    assert not same.added and not same.removed and same.changed


def test_render_collapses_subtrees_and_type_renames() -> None:
    """The document lists a block once and omits following renames."""
    text = deltas.render(
        [deltas.compute("pain.001.001.08", "pain.001.001.09")]
    )
    assert "## pain.001.001.08 → pain.001.001.09" in text
    assert "paths below)" in text
    assert "type renames that follow a parent's omitted" in text
    assert "### Choice branches added" in text


def test_render_reports_no_change_for_identical_inventories() -> None:
    """A step with nothing to say says so."""
    d = deltas.compute("pain.001.001.13", "pain.001.001.13")
    assert "No structural change." in deltas.render([d])
    assert "| 0 | 0 | 0 | +0 / −0 |" in deltas.render([d])


def test_describe_covers_every_facet_kind() -> None:
    """Enumerations, patterns, lengths and digits all render."""
    from pain001.corpus import inventory_for

    entries = {
        deltas._relative(e.path): e
        for e in inventory_for("pain.001.001.09").elements
    }
    assert "enum DEBT/CRED/SHAR/SLEV" in deltas._describe(
        entries["PmtInf/ChrgBr"]
    )
    assert "pattern `[A-Z]{3,3}`" in deltas._describe(
        entries[f"{CCT}/Amt/InstdAmt/@Ccy"]
    )
    assert "min length 1, max length 35" in deltas._describe(
        entries["GrpHdr/MsgId"]
    )
    assert "1..n" in deltas._describe(entries["PmtInf"])
    assert deltas._relative("/Document") == "/Document"
