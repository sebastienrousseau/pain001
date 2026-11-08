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

"""Never publish an invalid or partial payment file.

A payment file that appears at its destination is picked up: by a
watcher, an SFTP push, an operator. Every writer therefore stages the
bytes in a temporary file next to the destination, fsyncs it, and
renames it into place only once every check passed; on any failure the
temporary file is removed and the destination is left as it was.
"""

from __future__ import annotations

import csv
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from pain001.core.core import process_files, process_files_streaming
from pain001.exceptions import PaymentValidationError, XMLGenerationError
from pain001.plugins._builtins import _XmlFileWriter
from pain001.xml import publish
from pain001.xml.generate_xml import generate_xml, stream_xml_to_file

TYPE = "pain.001.001.03"
FOLDER = (Path("pain001/templates") / TYPE).resolve()
TEMPLATE = str(FOLDER / "template.xml")
XSD = str(FOLDER / f"{TYPE}.xsd")


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in ``tmp_path``: the batch loader only reads below the cwd."""
    monkeypatch.chdir(tmp_path)


def _rows() -> list[dict[str, Any]]:
    """The bundled .03 sample rows (one debtor, four transactions)."""
    with (FOLDER / "template.csv").open(encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write ``rows`` as a CSV file at ``path``."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _listing(folder: Path) -> list[str]:
    """Every entry in ``folder``, hidden temporary files included."""
    return sorted(entry.name for entry in folder.iterdir())


# --- stream_xml_to_file -------------------------------------------------


def test_stream_to_file_refuses_xsd_invalid_output(tmp_path: Path) -> None:
    """An XSD-invalid stream is refused and never becomes visible."""
    rows = _rows()
    rows[0]["payment_currency"] = rows[0]["currency"] = "EURO"
    out = tmp_path / "out"
    with pytest.raises(RuntimeError, match="failed validation"):
        stream_xml_to_file(rows, TYPE, TEMPLATE, str(out / "s.xml"))
    assert _listing(out) == []


def test_stream_to_file_leaves_nothing_on_a_render_error(
    tmp_path: Path,
) -> None:
    """A refusal raised while rendering leaves no empty file behind."""
    rows = _rows()
    rows[1]["debtor_name"] = "Another Debtor"
    with pytest.raises(PaymentValidationError, match="debtor_name"):
        stream_xml_to_file(rows, TYPE, TEMPLATE, str(tmp_path / "s.xml"))
    assert not (tmp_path / "s.xml").exists()


def test_stream_to_file_validates_rows(tmp_path: Path) -> None:
    """Rows are checked against the message type's column contract."""
    rows = _rows()
    rows[2]["date"] = "not-a-date"
    with pytest.raises(PaymentValidationError, match="validation failed"):
        stream_xml_to_file(rows, TYPE, TEMPLATE, str(tmp_path / "s.xml"))
    assert not (tmp_path / "s.xml").exists()


def test_stream_to_file_validates_its_output_path() -> None:
    """The output path goes through the path validator."""
    with pytest.raises(ValueError, match="Invalid output path"):
        stream_xml_to_file(_rows(), TYPE, TEMPLATE, "../escape.xml")


def test_stream_to_file_validates_an_explicit_schema_path(
    tmp_path: Path,
) -> None:
    """A given schema is used, and a missing one is refused up front."""
    written = stream_xml_to_file(
        _rows(), TYPE, TEMPLATE, str(tmp_path / "x.xml"), xsd_schema_path=XSD
    )
    assert Path(written).is_file()
    with pytest.raises(ValueError, match="Invalid schema path"):
        stream_xml_to_file(
            _rows(),
            TYPE,
            TEMPLATE,
            str(tmp_path / "y.xml"),
            xsd_schema_path=str(tmp_path / "missing.xsd"),
        )
    assert _listing(tmp_path) == ["x.xml"]


def test_stream_to_file_publishes_a_valid_file(tmp_path: Path) -> None:
    """The happy path still writes the full, valid document."""
    written = stream_xml_to_file(
        _rows(), TYPE, TEMPLATE, str(tmp_path / "ok.xml")
    )
    assert Path(written).read_text(encoding="utf-8").endswith("</Document>")
    assert _listing(tmp_path) == ["ok.xml"]


# --- the staging primitive ----------------------------------------------


def test_publish_text_stages_next_to_the_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The temporary file is a sibling, fsynced before the rename."""
    calls: list[tuple[str, Any]] = []
    real_replace, real_fsync = os.replace, os.fsync

    def replace(src: str, dst: str) -> None:
        calls.append(("replace", (os.path.dirname(src), Path(src).name)))
        real_replace(src, dst)

    def fsync(fd: int) -> None:
        calls.append(("fsync", fd))
        real_fsync(fd)

    monkeypatch.setattr(publish.os, "replace", replace)
    monkeypatch.setattr(publish.os, "fsync", fsync)
    target = tmp_path / "deep" / "file.xml"
    written = publish.publish_text("<a/>", str(target))
    assert written == str(target.resolve())
    assert target.read_text(encoding="utf-8") == "<a/>"
    assert [name for name, _ in calls] == ["fsync", "replace"]
    folder, name = calls[1][1]
    assert folder == str(target.parent.resolve())
    assert name.startswith(".file.xml.") and name.endswith(".tmp")


def test_publish_text_honours_the_umask(tmp_path: Path) -> None:
    """The published file is 0o644 narrowed by the umask, never writable
    by others."""
    umask = os.umask(0o022)
    try:
        written = publish.publish_text("<a/>", str(tmp_path / "m.xml"))
    finally:
        os.umask(umask)
    assert stat.S_IMODE(os.stat(written).st_mode) == 0o644


def test_publish_text_is_never_world_writable(tmp_path: Path) -> None:
    """Even with an empty umask, others cannot write a payment file."""
    umask = os.umask(0)
    try:
        written = publish.publish_text("<a/>", str(tmp_path / "w.xml"))
    finally:
        os.umask(umask)
    assert stat.S_IMODE(os.stat(written).st_mode) == 0o644


@pytest.mark.parametrize("failing", ["write", "fsync", "replace"])
def test_publish_text_failure_keeps_the_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    """A failure at any step removes the temp file, keeps the old one."""
    target = tmp_path / "keep.xml"
    target.write_text("old", encoding="utf-8")

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(f"{failing} failed")

    if failing == "write":
        monkeypatch.setattr(publish, "_write_all", boom)
    else:
        monkeypatch.setattr(publish.os, failing, boom)
    with pytest.raises(OSError, match=f"{failing} failed"):
        publish.publish_text("new", str(target))
    assert target.read_text(encoding="utf-8") == "old"
    assert _listing(tmp_path) == ["keep.xml"]


def test_publish_stream_check_failure_publishes_nothing(
    tmp_path: Path,
) -> None:
    """The check sees the staged file; its refusal removes it."""
    seen: list[str] = []

    def check(path: str) -> None:
        seen.append(Path(path).read_text(encoding="utf-8"))
        raise RuntimeError("refused")

    with pytest.raises(RuntimeError, match="refused"):
        publish.publish_stream(
            iter(["<a>", "</a>"]), str(tmp_path / "x"), check
        )
    assert seen == ["<a></a>"]
    assert _listing(tmp_path) == []


# --- generate_xml and the plugin writer ----------------------------------


def test_generate_xml_write_failure_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed fsync during generate_xml publishes no file."""

    def boom(_fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(publish.os, "fsync", boom)
    with pytest.raises(OSError, match="disk full"):
        generate_xml(_rows(), TYPE, TEMPLATE, XSD, str(tmp_path / "g.xml"))
    assert _listing(tmp_path) == []


def test_xml_file_writer_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The built-in xml-file writer stages and renames too."""
    target = tmp_path / "w.xml"
    target.write_text("old", encoding="utf-8")

    def boom(_src: str, _dst: str) -> None:
        raise OSError("rename failed")

    monkeypatch.setattr(publish.os, "replace", boom)
    with pytest.raises(OSError, match="rename failed"):
        _XmlFileWriter().write("<new/>", str(target))
    assert target.read_text(encoding="utf-8") == "old"
    assert _listing(tmp_path) == ["w.xml"]


# --- Schematron runs before the file is published ------------------------


def _usd_rows() -> list[dict[str, Any]]:
    """XSD-valid rows that break SEPA (non-EUR currency)."""
    rows = _rows()
    for row in rows:
        row["currency"] = row["payment_currency"] = "USD"
    return rows


def test_process_files_schematron_failure_publishes_nothing(
    tmp_path: Path,
) -> None:
    """A Schematron refusal leaves no file at the output path."""
    data = _write_csv(tmp_path / "usd.csv", _usd_rows())
    out = tmp_path / "out" / "p.xml"
    with pytest.raises(XMLGenerationError, match="Schematron rulebook"):
        process_files(
            TYPE, TEMPLATE, XSD, str(data), str(out), schematron="sepa"
        )
    assert not out.parent.exists() or _listing(out.parent) == []


def test_streaming_schematron_failure_publishes_no_chunk(
    tmp_path: Path,
) -> None:
    """A chunk Schematron refuses is never written."""
    data = _write_csv(tmp_path / "usd.csv", _usd_rows())
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(XMLGenerationError, match="Schematron validation"):
        process_files_streaming(
            TYPE,
            TEMPLATE,
            XSD,
            str(data),
            chunk_size=10,
            output_dir=str(out),
            schematron="sepa",
        )
    assert _listing(out) == []


def test_streaming_chunk_write_failure_leaves_no_partial_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chunk whose write fails is not left half-written."""
    data = _write_csv(tmp_path / "in.csv", _rows())
    out = tmp_path / "out"
    out.mkdir()

    def boom(_fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(publish.os, "fsync", boom)
    with pytest.raises(OSError, match="disk full"):
        process_files_streaming(
            TYPE, TEMPLATE, XSD, str(data), 10, output_dir=str(out)
        )
    assert _listing(out) == []
