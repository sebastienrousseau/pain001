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

"""The bundled example XML and SQLite mirrors cannot drift any more.

Before 0.0.67 nothing validated ``pain001/templates/<type>/<type>.xml``
beyond a substring check, and two of them carried a block the template
could not emit; ``template.db`` for pain.008 had no regeneration path
at all. These tests pin each example to the rendering of its own
``template.csv`` and each database to its CSV, using the same scripts
that regenerate them.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from pain001.constants import valid_xml_types
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_xml_examples  # noqa: E402
import regenerate_template_dbs  # noqa: E402


def _swap(monkeypatch: pytest.MonkeyPatch, message_type: str, **changes):
    """Replace one registry entry for the test's duration."""
    registry = DEFAULT_TEMPLATE_REGISTRY._registry
    patched = dict(registry)
    patched[message_type] = replace(registry[message_type], **changes)
    monkeypatch.setattr(DEFAULT_TEMPLATE_REGISTRY, "_registry", patched)
    return patched[message_type]


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_bundled_example_is_the_rendering_of_its_template_csv(
    message_type: str,
) -> None:
    """The committed example equals the script's output byte for byte."""
    out, xml = generate_xml_examples.render_example(message_type)
    assert out.exists(), f"{out} missing; run generate_xml_examples.py"
    assert out.read_text(encoding="utf-8") == xml, (
        f"{out.name} is stale; run scripts/generate_xml_examples.py"
    )


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_bundled_example_validates_against_its_xsd(
    message_type: str,
) -> None:
    """Every example is valid against the XSD next to it."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    assert meta.example_xml_path is not None
    xml = meta.example_xml_path.read_text(encoding="utf-8")
    assert validate_xml_string_via_xsd(xml, str(meta.xsd_path))
    assert "<WC" not in xml, "the hand-edited SplmtryData block is back"


@pytest.mark.parametrize("message_type", valid_xml_types)
def test_template_db_mirrors_template_csv(message_type: str) -> None:
    """The SQLite mirror has the CSV's columns and rows, in order."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
    base = meta.template_path.parent
    columns, rows = regenerate_template_dbs._rows_and_columns(
        base / "template.csv"
    )
    assert columns and rows
    assert regenerate_template_dbs._db_contents(base / "template.db") == (
        columns,
        rows,
    ), f"{base.name}/template.db stale; run regenerate_template_dbs.py"


def test_check_modes_pass_on_a_clean_tree(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--check`` on both scripts exits 0 when nothing is stale."""
    assert generate_xml_examples.main(["--check"]) == 0
    assert regenerate_template_dbs.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "STALE" not in out
    assert out.count("up to date") == 2 * len(valid_xml_types)


def test_check_mode_reports_a_stale_example(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A stale example makes ``--check`` exit 1 and name the file."""
    stale = tmp_path / "pain.001.001.03.xml"
    stale.write_text("<stale/>", encoding="utf-8")
    _swap(monkeypatch, "pain.001.001.03", example_xml_path=stale)
    assert generate_xml_examples.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "STALE" in out and "1 stale example" in out
    assert stale.read_text(encoding="utf-8") == "<stale/>", "check wrote"


def test_regenerate_writes_a_missing_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ``--check`` the script writes the rendering to the path.

    With no ``example_xml_path`` or ``example_data_path`` in metadata the
    script falls back to ``<type>.xml`` and ``template.csv`` next to the
    template, so both fallbacks are exercised here.
    """
    real = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03")
    bundle = tmp_path / "pain.001.001.03"
    bundle.mkdir()
    for name in ("template.xml", "template.csv", "pain.001.001.03.xsd"):
        (bundle / name).write_bytes(
            (real.template_path.parent / name).read_bytes()
        )
    _swap(
        monkeypatch,
        "pain.001.001.03",
        template_path=bundle / "template.xml",
        xsd_path=bundle / "pain.001.001.03.xsd",
        example_data_path=None,
        example_xml_path=None,
    )
    assert generate_xml_examples.main([]) == 0
    written = bundle / "pain.001.001.03.xml"
    assert written.exists()
    assert validate_xml_string_via_xsd(
        written.read_text(encoding="utf-8"), str(real.xsd_path)
    )
    assert written.read_bytes() == (
        real.example_xml_path.read_bytes()  # type: ignore[union-attr]
    )


def test_rebuild_writes_a_fresh_mirror(tmp_path: Path) -> None:
    """``rebuild`` produces a database that reads back identically."""
    db = tmp_path / "template.db"
    cols = ["id", "payment_amount"]
    rows = [["1", "10.00"], ["2", "20.50"]]
    regenerate_template_dbs.rebuild(db, cols, rows)
    assert regenerate_template_dbs._db_contents(db) == (cols, rows)
    # A second rebuild replaces rather than appends.
    regenerate_template_dbs.rebuild(db, cols, rows[:1])
    assert regenerate_template_dbs._db_contents(db) == (cols, rows[:1])


def test_db_contents_tolerates_missing_or_corrupt_files(
    tmp_path: Path,
) -> None:
    """A missing or non-SQLite file reads as empty, so it counts as stale."""
    missing = regenerate_template_dbs._db_contents(tmp_path / "nope.db")
    assert missing == ([], [])
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database")
    assert regenerate_template_dbs._db_contents(junk) == ([], [])


def test_check_mode_reports_a_stale_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A database that disagrees with its CSV makes ``--check`` exit 1."""
    real = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.008.001.02")
    bundle = tmp_path / "pain.008.001.02"
    bundle.mkdir()
    (bundle / "template.csv").write_bytes(
        (real.template_path.parent / "template.csv").read_bytes()
    )
    conn = sqlite3.connect(bundle / "template.db")
    conn.execute('CREATE TABLE "pain001" ("id" TEXT)')
    conn.commit()
    conn.close()
    _swap(monkeypatch, "pain.008.001.02", template_path=bundle / "t.xml")
    assert regenerate_template_dbs.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "STALE" in out and "1 stale database" in out
    # A rebuild brings it in line and the next check is clean.
    assert regenerate_template_dbs.main([]) == 0
    assert "rebuilt" in capsys.readouterr().out
    assert regenerate_template_dbs.main(["--check"]) == 0
