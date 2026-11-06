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

"""The ISO 2018 face's name table and the script that builds it (ADR-0005)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = """
        GroupHeader <GrpHdr>                    [1..1]
        Or IBAN <IBAN>                          [1..1]
        Message root <Document> <CstmrCdtTrfInitn>
"""


@pytest.fixture(scope="module")
def script() -> ModuleType:
    """``scripts/build_iso_name_table.py`` as a module."""
    spec = importlib.util.spec_from_file_location(
        "build_iso_name_table", ROOT / "scripts" / "build_iso_name_table.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_shipped_table_accounts_for_every_bundled_tag(
    script: ModuleType,
) -> None:
    """``--check`` passes: every tag is named or listed with a reason."""
    assert script.main(["--check"]) == 0


def test_reports_yield_name_tag_pairs_without_layout_words(
    script: ModuleType,
) -> None:
    """``Or`` and ``Message root`` are the report's layout, not names."""
    assert script.read_pairs(REPORT) == [
        ("GroupHeader", "GrpHdr"),
        ("IBAN", "IBAN"),
    ]


def test_a_tag_with_two_names_stops_the_build(script: ModuleType) -> None:
    """The table is only built when every report agrees."""
    with pytest.raises(SystemExit, match="more than one name"):
        script.names_from_reports(
            {"a.pdf": "GroupHeader <GrpHdr>", "b.pdf": "GroupHeading <GrpHdr>"}
        )


def test_build_lists_what_no_report_names(script: ModuleType) -> None:
    """A bundled tag absent from the reports is unresolved, with a reason."""
    tags = {"pain.001.001.03": {"Document", "GrpHdr", "BIC", "Zzz"}}
    table = script.build_table({"r.pdf": REPORT}, "2026-11-06", tags)
    assert table["names"] == {"GrpHdr": "GroupHeader"}
    assert set(table["unresolved"]) == {"BIC", "Zzz"}
    assert "2009" in table["unresolved"]["BIC"]
    assert table["reports"] == ["r.pdf"] and table["read_date"] == "2026-11-06"
    assert script.check(table, tags) == []


def test_check_reports_gaps_and_missing_provenance(script: ModuleType) -> None:
    """An incomplete table is caught before it ships."""
    tags = {"v": {"GrpHdr", "Nm"}}
    broken = {
        "names": {"GrpHdr": "GroupHeader"},
        "unresolved": {"GrpHdr": "x"},
    }
    problems = script.check(broken, tags)
    assert "v: Nm is neither named nor listed as unresolved" in problems
    assert "GrpHdr is both named and unresolved" in problems
    assert "missing provenance field 'read_date'" in problems
    assert script.check({}, tags) == [
        "the table needs 'names' and 'unresolved' objects"
    ]


def test_the_shipped_table_is_the_one_the_face_reads() -> None:
    """The packaged file is valid JSON with recorded provenance."""
    table = json.loads(
        (ROOT / "pain001" / "faces" / "iso_names.json").read_text(
            encoding="utf-8"
        )
    )
    assert table["read_date"] == "2026-11-06"
    assert all(r.endswith(".pdf") for r in table["reports"])
