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

"""Chunked streaming: one distinct message per file, rows validated.

``process_files_streaming`` writes one XML file per chunk. Each file is
a message of its own, so each needs its own GrpHdr/MsgId (and PmtInfId
when the rows name one); a bank rejects the second file of a run whose
id repeats. The rows of every chunk pass the same validation the batch
path applies.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pytest

from pain001.core.chunks import chunk_identifier, numbered_chunks
from pain001.core.core import process_files, process_files_streaming
from pain001.exceptions import PaymentValidationError

TYPE = "pain.001.001.03"
FOLDER = (Path("pain001/templates") / TYPE).resolve()
TEMPLATE = str(FOLDER / "template.xml")
XSD = str(FOLDER / f"{TYPE}.xsd")


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in ``tmp_path``: the batch loader only reads below the cwd."""
    monkeypatch.chdir(tmp_path)


def _rows(message_id: str = "MSG001") -> list[dict[str, Any]]:
    """The bundled .03 sample, every row in one message ``message_id``."""
    with (FOLDER / "template.csv").open(encoding="utf-8", newline="") as fh:
        rows = [dict(row) for row in csv.DictReader(fh)]
    for row in rows:
        row["id"] = message_id
    return rows


def _write(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write ``rows`` as a CSV file at ``path``."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _ids(xml_path: str) -> tuple[str, str]:
    """The (MsgId, PmtInfId) of a generated file."""
    text = Path(xml_path).read_text(encoding="utf-8")
    msg = re.search(r"<MsgId>([^<]*)</MsgId>", text)
    pmt = re.search(r"<PmtInfId>([^<]*)</PmtInfId>", text)
    assert msg and pmt
    return msg.group(1), pmt.group(1)


def _stream(data: Path, out: Path, chunk_size: int) -> list[str]:
    """Run the chunked pipeline on ``data`` into ``out``."""
    out.mkdir(exist_ok=True)
    return process_files_streaming(
        TYPE, TEMPLATE, XSD, str(data), chunk_size, output_dir=str(out)
    )


def test_every_chunk_gets_its_own_message_and_batch_id(
    tmp_path: Path,
) -> None:
    """Chunk n carries ``<id>-<n>`` and ``<PmtInfId>-<n>``."""
    data = _write(tmp_path / "in.csv", _rows())
    paths = _stream(data, tmp_path / "out", chunk_size=1)
    assert [_ids(p) for p in paths] == [
        (f"MSG001-{n}", f"Payment-Info-12345-{n}") for n in range(1, 5)
    ]


def test_chunk_ids_stay_within_max35text(tmp_path: Path) -> None:
    """A 35-character id is cut so ``<id>-<n>`` still fits (XSD-valid)."""
    long_id = "M" * 35
    data = _write(tmp_path / "in.csv", _rows(long_id))
    paths = _stream(data, tmp_path / "out", chunk_size=2)
    assert [_ids(p)[0] for p in paths] == ["M" * 33 + "-1", "M" * 33 + "-2"]


def test_chunk_identifier_truncates_deterministically() -> None:
    """The base is cut, never the suffix; blank stays blank."""
    assert chunk_identifier("ABC", 7) == "ABC-7"
    assert chunk_identifier("X" * 40, 12) == "X" * 32 + "-12"
    assert chunk_identifier("", 3) == ""
    assert chunk_identifier("  ", 3) == "  "


def test_numbered_chunks_leaves_a_single_chunk_alone() -> None:
    """One chunk is the whole message: its ids are not renamed."""
    only = [{"id": "A", "payment_information_id": "P"}]
    assert list(numbered_chunks(iter([only]))) == [(1, only)]
    assert list(numbered_chunks(iter([]))) == []


def test_numbered_chunks_does_not_mutate_the_input() -> None:
    """The caller's rows keep their ids; the chunks get copies."""
    first = [{"id": "A", "payment_information_id": ""}]
    second = [{"id": "A"}]
    numbered = list(numbered_chunks(iter([first, second])))
    assert numbered == [
        (1, [{"id": "A-1", "payment_information_id": ""}]),
        (2, [{"id": "A-2"}]),
    ]
    assert first == [{"id": "A", "payment_information_id": ""}]


def test_single_chunk_is_byte_identical_to_the_batch_file(
    tmp_path: Path,
) -> None:
    """A run that fits one chunk writes exactly what process_files does."""
    data = _write(tmp_path / "in.csv", _rows())
    (streamed,) = _stream(data, tmp_path / "out", chunk_size=100)
    batch = process_files(
        TYPE, TEMPLATE, XSD, str(data), output_path=str(tmp_path / "b.xml")
    )
    assert Path(streamed).read_bytes() == Path(batch).read_bytes()


def test_chunked_output_is_deterministic(tmp_path: Path) -> None:
    """Two runs over the same input produce the same files."""
    data = _write(tmp_path / "in.csv", _rows())
    first = _stream(data, tmp_path / "one", chunk_size=3)
    second = _stream(data, tmp_path / "two", chunk_size=3)
    assert [Path(p).read_bytes() for p in first] == [
        Path(p).read_bytes() for p in second
    ]


def test_streamed_rows_get_the_batch_validation(tmp_path: Path) -> None:
    """A row the batch path refuses is refused when streamed too.

    ``forwarding_agent_BIC`` is never rendered, so only the row
    validation (not the XSD) can catch its absence.
    """
    rows = _rows()
    rows[2]["forwarding_agent_BIC"] = ""
    data = _write(tmp_path / "bad.csv", rows)
    with pytest.raises(PaymentValidationError):
        process_files(
            TYPE, TEMPLATE, XSD, str(data), output_path=str(tmp_path / "b")
        )
    with pytest.raises(PaymentValidationError):
        _stream(data, tmp_path / "out", chunk_size=2)
