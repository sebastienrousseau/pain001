# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Streamed chunks built by several worker processes.

The files must be the ones a single process writes, in the same order,
and a failure must leave what the sequential run leaves: the chunks
before the failing one, and nothing after it.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.core._parallel import build_chunks
from pain001.core.core import process_files_streaming
from pain001.exceptions import XMLGenerationError

MT = "pain.001.001.09"
BUNDLE = TEMPLATES_DIR / MT


def _write_rows(path: Path, chunks: int, usd_chunk: int | None = None) -> None:
    """Two rows per chunk; ``usd_chunk`` (1-based) pays in USD."""
    with (BUNDLE / "template.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        base = next(iter(reader))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for n in range(chunks * 2):
            row = dict(base, payment_id=f"P{n}", id=str(n + 1))
            if usd_chunk is not None and n // 2 + 1 == usd_chunk:
                row["payment_currency"] = row["currency"] = "USD"
            writer.writerow(row)


def _run(tmp_path: Path, workers: int, **kwargs: object) -> list[str]:
    out = tmp_path / f"out{workers}"
    return process_files_streaming(
        MT,
        str(BUNDLE / "template.xml"),
        str(BUNDLE / f"{MT}.xsd"),
        str(tmp_path / "rows.csv"),
        chunk_size=2,
        output_dir=str(out),
        workers=workers,
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("workers", [2, 4])
def test_workers_write_the_same_files_in_the_same_order(
    workdir: Path, workers: int
) -> None:
    """Two workers keep at most four chunks in flight, so five refill."""
    _write_rows(workdir / "rows.csv", chunks=5)
    one = _run(workdir, 1)
    many = _run(workdir, workers)
    assert [Path(p).name for p in many] == [Path(p).name for p in one]
    assert len(many) == 5
    for a, b in zip(one, many, strict=True):
        assert Path(a).read_bytes() == Path(b).read_bytes()


@pytest.mark.parametrize("workers", [1, 3])
def test_a_failing_chunk_leaves_only_the_chunks_before_it(
    workdir: Path, workers: int
) -> None:
    _write_rows(workdir / "rows.csv", chunks=5, usd_chunk=2)
    with pytest.raises(XMLGenerationError, match="chunk0002"):
        _run(workdir, workers, schematron="sepa")
    published = sorted(
        p.name for p in (workdir / f"out{workers}").glob("*.xml")
    )
    assert published == [f"{MT}.chunk0001.xml"]
    assert not list((workdir / f"out{workers}").glob("*.tmp"))


def test_workers_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        list(build_chunks([], workers=0))


def test_no_chunks_builds_nothing_with_workers() -> None:
    assert list(build_chunks([], workers=2)) == []


def test_discarding_removes_later_published_chunks(tmp_path: Path) -> None:
    from collections import deque
    from concurrent.futures import Future

    from pain001.core._parallel import Built, _discard_later

    published = tmp_path / "x.chunk0003.xml"
    published.write_text("<x/>", encoding="utf-8")
    done: Future[Built] = Future()
    done.set_result((3, str(published), 2))
    gone: Future[Built] = Future()
    gone.set_result((4, str(tmp_path / "already-removed.xml"), 2))
    failed: Future[Built] = Future()
    failed.set_exception(RuntimeError("boom"))
    queued: Future[Built] = Future()
    _discard_later(deque([done, gone, failed, queued]))
    assert not published.exists()
    assert queued.cancelled()


def test_the_cli_passes_workers_to_streaming(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    monkeypatch.setenv("PAIN001_WORKERS", "1")

    from pain001.cli.cli import cli

    _write_rows(workdir / "rows.csv", chunks=3)
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            MT,
            "-d",
            "rows.csv",
            "-o",
            "out",
            "--streaming",
            "--chunk-size",
            "2",
            "--workers",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(list((workdir / "out").glob("*.chunk*.xml"))) == 3


def test_the_flag_sets_pain001_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from pain001.cli._gpg import _workers_option

    # setenv records the variable's absence, so teardown removes what
    # the callback writes.
    monkeypatch.setenv("PAIN001_WORKERS", "1")
    monkeypatch.delenv("PAIN001_WORKERS")
    assert _workers_option(None, None, None) is None  # type: ignore[arg-type]
    assert "PAIN001_WORKERS" not in os.environ
    assert _workers_option(None, None, 3) == 3  # type: ignore[arg-type]
    assert os.environ["PAIN001_WORKERS"] == "3"


def test_streaming_reads_pain001_workers(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pain001.core import core

    seen: list[int] = []

    def fake(jobs: object, workers: int) -> list[object]:
        seen.append(workers)
        return []

    monkeypatch.setattr(core, "build_chunks", fake)
    _write_rows(workdir / "rows.csv", chunks=1)
    monkeypatch.setenv("PAIN001_WORKERS", "3")
    _run(workdir, None)  # type: ignore[arg-type]
    monkeypatch.delenv("PAIN001_WORKERS")
    _run(workdir, None)  # type: ignore[arg-type]
    _run(workdir, 2)
    assert seen == [3, 1, 2]
