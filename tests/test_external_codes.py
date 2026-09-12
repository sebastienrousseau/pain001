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

"""The vendored ISO external code sets and the refresh script."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pain001.corpus.rules import external_codes as x

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import refresh_external_codes  # noqa: E402


def test_edition_is_the_single_vendored_file() -> None:
    """The edition is the stem of the one JSON under data/external_codes."""
    assert x.edition() == "2Q2026_v3"
    assert x.edition_file().name == "2Q2026_v3.json"
    assert x.edition_file().parent == x.DATA_DIR


def test_sets_and_codes_match_the_document() -> None:
    """Names and enums come straight from the document's definitions."""
    definitions = x.load_definitions(x.edition_file())
    assert x.code_sets() == tuple(sorted(definitions))
    assert len(x.code_sets()) == 163
    assert "ExternalBankTransactionDomain1Code" in x.sets_without_codes()
    assert x.codes("ExternalServiceLevel1Code") == tuple(
        definitions["ExternalServiceLevel1Code"]["enum"]
    )
    assert x.is_valid("ExternalServiceLevel1Code", "SEPA")
    assert x.is_valid("ExternalServiceLevel1Code", "URGP")
    assert not x.is_valid("ExternalServiceLevel1Code", "sepa")
    assert x.is_valid("ExternalPurpose1Code", "SALA")
    assert x.is_valid("ExternalCategoryPurpose1Code", "SUPP")
    assert x.is_valid("ExternalLocalInstrument1Code", "CORE")


def test_describe_parses_the_published_meaning() -> None:
    """Descriptions are the ``*`CODE`-text`` lines; unknown codes give None."""
    assert x.describe("ExternalCategoryPurpose1Code", "BONU") == (
        "Transaction is the payment of a bonus."
    )
    assert x.describe("ExternalCategoryPurpose1Code", "ZZZZ") is None


def test_unknown_or_codeless_set_raises() -> None:
    """A set the edition does not enumerate cannot be queried for codes."""
    with pytest.raises(KeyError, match="not an external code set"):
        x.codes("ExternalNoSuchCode")
    with pytest.raises(KeyError):
        x.codes("ExternalBankTransactionDomain1Code")
    with pytest.raises(KeyError):
        x.describe("ExternalNoSuchCode", "AAAA")


def test_edition_file_requires_exactly_one(tmp_path: Path) -> None:
    """Zero or two editions in the directory is an error, not a guess."""
    with pytest.raises(FileNotFoundError, match="exactly one"):
        x.edition_file(tmp_path)
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="exactly one"):
        x.edition_file(tmp_path)


def _edition(
    tmp_path: Path, name: str, sets: dict[str, list[str] | None]
) -> Path:
    definitions = {
        s: ({"type": "string", "enum": codes} if codes else {"type": "string"})
        for s, codes in sets.items()
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"definitions": definitions}), encoding="utf-8")
    return path


def test_diff_editions_reports_every_kind_of_change() -> None:
    """Added and withdrawn codes, new and dropped sets."""
    old = {"A": {"enum": ["X", "Y"]}, "B": {"enum": ["P"]}, "C": {}}
    new = {
        "A": {"enum": ["Y", "Z"]},
        "C": {"enum": ["Q"]},
        "D": {"enum": ["R"]},
    }
    added, withdrawn, new_sets, dropped = refresh_external_codes.diff_editions(
        old, new
    )
    assert added == {"A": ["Z"], "C": ["Q"], "D": ["R"]}
    assert withdrawn == {"A": ["X"], "B": ["P"]}
    assert new_sets == ["D"] and dropped == ["B"]


def test_usages_finds_xml_values_and_csv_cells(tmp_path: Path) -> None:
    """A code counts as used only as a whole XML value or CSV cell."""
    (tmp_path / "a.xml").write_text("<Cd>SEPA</Cd>")
    (tmp_path / "b.csv").write_text("id,code\n1,SEPA\n")
    (tmp_path / "c.csv").write_text("id,code\n1,SEPAX\n")
    (tmp_path / "d.txt").write_text(">SEPA<")
    assert refresh_external_codes.usages("SEPA", (tmp_path,)) == [
        tmp_path / "a.xml",
        tmp_path / "b.csv",
    ]
    assert refresh_external_codes.usages("NOPE", (tmp_path,)) == []


def test_refresh_replaces_when_nothing_in_use_is_withdrawn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Adding codes, or withdrawing unused ones, swaps the edition."""
    data = tmp_path / "data"
    data.mkdir()
    _edition(data, "1Q2026_v1", {"S": ["AAAA", "BBBB"]})
    new = _edition(tmp_path, "2Q2026_v1", {"S": ["AAAA", "CCCC"], "T": None})
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "x.xml").write_text("<Cd>AAAA</Cd>")
    argv = [str(new), "--data-dir", str(data), "--scan", str(scan)]
    assert refresh_external_codes.main(argv + ["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "+ S: CCCC" in out and "- S: BBBB" in out and "dry run" in out
    assert (data / "1Q2026_v1.json").exists()
    assert refresh_external_codes.main(argv) == 0
    assert sorted(p.name for p in data.glob("*.json")) == ["2Q2026_v1.json"]
    assert "vendored 2Q2026_v1.json" in capsys.readouterr().out
    # Re-running with the same file name overwrites in place.
    assert refresh_external_codes.main(argv) == 0
    assert sorted(p.name for p in data.glob("*.json")) == ["2Q2026_v1.json"]


def test_refresh_refuses_when_a_used_code_is_withdrawn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A withdrawn code still present in bundled data blocks the swap."""
    data = tmp_path / "data"
    data.mkdir()
    _edition(data, "old", {"S": ["AAAA", "BBBB"]})
    new = _edition(tmp_path, "new", {"S": ["AAAA"]})
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "t.csv").write_text("id,code\n1,BBBB\n")
    argv = [str(new), "--data-dir", str(data), "--scan", str(scan)]
    assert refresh_external_codes.main(argv) == 1
    out = capsys.readouterr().out
    assert "BLOCKED S: BBBB used in" in out and "not replaced" in out
    assert (data / "old.json").exists() and not (data / "new.json").exists()


def test_refresh_default_scan_roots_are_the_bundled_data() -> None:
    """The real scan roots exist and include the templates."""
    assert all(p.is_dir() for p in refresh_external_codes.DEFAULT_SCAN[:1])
    assert refresh_external_codes.DEFAULT_SCAN[0].name == "templates"
    # The vendored edition against itself: nothing withdrawn, nothing blocked.
    assert (
        refresh_external_codes.main([str(x.edition_file()), "--dry-run"]) == 0
    )
