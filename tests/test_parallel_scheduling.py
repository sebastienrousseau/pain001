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

"""Chunk scheduling and the per-chunk build, checked in this process.

``tests/test_parallel_chunks.py`` runs real worker processes, which the
mutation run cannot host. Here an inline executor stands in for the
process pool, so the scheduling contract is checked directly: a spawn
context, ``workers`` processes, at most twice as many chunks in flight,
results in chunk order, and on a failure the later published chunks are
removed. A chunk is also built for real in this process, from a
template and schema outside the path jail, as the command line allows.
"""

from __future__ import annotations

import multiprocessing
import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.core import _parallel
from pain001.core._parallel import Built, ChunkJob, build_chunk, build_chunks
from pain001.data.loader import load_payment_data
from pain001.security.path_validator import SecurityError, validate_path

MT = "pain.001.001.09"


class _InlinePool:
    """A process-pool stand-in that runs each job when it is submitted."""

    def __init__(self, max_workers: int, mp_context: Any) -> None:
        self.max_workers = max_workers
        self.mp_context = mp_context
        self.submitted: list[int] = []

    def __enter__(self) -> _InlinePool:
        """Enter the pool."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Leave the pool."""

    def submit(self, fn: Callable[..., Built], *args: Any) -> Future[Built]:
        """Run ``fn`` now and return its settled future."""
        self.submitted.append(args[0].index)
        future: Future[Built] = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future


def _jobs(tmp_path: Path, count: int) -> list[ChunkJob]:
    """``count`` chunk jobs of one row each, writing under ``tmp_path``."""
    return [
        ChunkJob(i, [{"n": i}], MT, "t.xml", "s.xsd", str(tmp_path))
        for i in range(1, count + 1)
    ]


@pytest.fixture
def pools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[_InlinePool]:
    """Patch in the inline pool and a builder that writes a file per chunk.

    Chunk 3 fails. Returns the list of pools created.
    """
    created: list[_InlinePool] = []

    def pool(max_workers: int, mp_context: Any) -> _InlinePool:
        created.append(_InlinePool(max_workers, mp_context))
        return created[-1]

    def fake_build(job: ChunkJob) -> Built:
        if job.index == 3:
            raise RuntimeError("chunk 3 failed")
        path = tmp_path / f"chunk{job.index}.xml"
        path.write_text("<x/>", encoding="utf-8")
        return job.index, str(path), len(job.rows)

    monkeypatch.setattr(_parallel, "ProcessPoolExecutor", pool)
    monkeypatch.setattr(_parallel, "build_chunk", fake_build)
    return created


def test_one_worker_by_default_builds_in_this_process(
    tmp_path: Path, pools: list[_InlinePool]
) -> None:
    """Without ``workers`` no pool is started and chunks come back in order."""
    built = list(build_chunks(_jobs(tmp_path, 2)))
    assert built == [
        (1, str(tmp_path / "chunk1.xml"), 1),
        (2, str(tmp_path / "chunk2.xml"), 1),
    ]
    assert pools == []


def test_two_workers_keep_four_chunks_in_flight(
    tmp_path: Path, pools: list[_InlinePool]
) -> None:
    """Spawned workers, two of them, four chunks ahead, results in order."""
    jobs = [job for job in _jobs(tmp_path, 7) if job.index != 3]
    results = build_chunks(jobs, workers=2)
    first = next(results)
    (pool,) = pools
    assert pool.max_workers == 2
    assert pool.mp_context is multiprocessing.get_context("spawn")
    assert pool.submitted == [1, 2, 4, 5, 6]
    assert first == (1, str(tmp_path / "chunk1.xml"), 1)
    assert [index for index, _, _ in results] == [2, 4, 5, 6, 7]
    assert pool.submitted == [1, 2, 4, 5, 6, 7]


def test_a_failed_chunk_removes_the_later_published_ones(
    tmp_path: Path, pools: list[_InlinePool]
) -> None:
    """Chunks before the failure stay; those already built after it go."""
    results = build_chunks(_jobs(tmp_path, 6), workers=2)
    assert [next(results)[0], next(results)[0]] == [1, 2]
    with pytest.raises(RuntimeError, match="chunk 3 failed"):
        next(results)
    assert sorted(p.name for p in tmp_path.glob("chunk*.xml")) == [
        "chunk1.xml",
        "chunk2.xml",
    ]


def test_workers_below_one_are_refused_by_name() -> None:
    """Zero workers is a ValueError that says what is required."""
    with pytest.raises(ValueError) as caught:
        list(build_chunks([], workers=0))
    assert str(caught.value) == "workers must be at least 1"


@pytest.fixture
def rows() -> list[dict[str, Any]]:
    """The bundled sample rows, loaded before any directory change."""
    return load_payment_data(str(TEMPLATES_DIR / MT / "template.csv"))


@pytest.fixture
def outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A directory outside every allowed base, with the bundle copied in.

    The working directory and the temporary directory are moved under
    ``tmp_path``; the bundle goes to a fresh directory under ``/tmp``,
    which is then none of the allowed bases.
    """
    root = Path(tempfile.mkdtemp(prefix="pain001-jail-", dir="/tmp"))
    bundle = TEMPLATES_DIR / MT
    shutil.copy(bundle / "template.xml", root)
    shutil.copy(bundle / f"{MT}.xsd", root)
    workdir = tmp_path / "work"
    (workdir / "out").mkdir(parents=True)
    (tmp_path / "temp").mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    yield root
    shutil.rmtree(root)


def test_a_chunk_is_built_from_files_outside_the_jail(
    rows: list[dict[str, Any]], outside: Path
) -> None:
    """The chunk trusts exactly its template and schema, and publishes."""
    template, schema = outside / "template.xml", outside / f"{MT}.xsd"
    with pytest.raises(SecurityError):
        validate_path(str(template))
    with pytest.raises(SecurityError):
        validate_path(str(schema))
    out = Path.cwd() / "out"
    job = ChunkJob(2, rows, MT, str(template), str(schema), str(out))
    index, path, count = build_chunk(job)
    assert (index, count) == (2, len(rows))
    assert path == os.path.join(str(out), f"{MT}.chunk0002.xml")
    assert "<Document" in Path(path).read_text(encoding="utf-8")


def test_a_chunk_is_finalised_with_the_jobs_envelope_and_keys(
    rows: list[dict[str, Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The BAH flag, header and signing material reach the finaliser."""
    from pain001.xml import publish

    seen: list[tuple[Any, ...]] = []

    def finalise(xml: str, *args: Any) -> str:
        seen.append(args)
        return xml

    monkeypatch.setattr(publish, "finalise_message", finalise)
    bundle = TEMPLATES_DIR / MT
    job = ChunkJob(
        1,
        rows,
        MT,
        str(bundle / "template.xml"),
        str(bundle / f"{MT}.xsd"),
        str(tmp_path),
        True,
        {"header": 1},
        "key",
        "cert",
        "secret",
    )
    build_chunk(job)
    assert seen == [(True, {"header": 1}, "key", "cert", "secret")]


def _built(path: Path) -> Future[Built]:
    """A finished chunk whose output is ``path``."""
    future: Future[Built] = Future()
    future.set_result((0, str(path), 1))
    return future


def test_discard_skips_cancelled_and_failed_then_unlinks_the_rest(
    tmp_path: Path,
) -> None:
    """After a failure, later chunks are cancelled; finished ones deleted."""
    from collections import deque

    queued: Future[Built] = Future()
    failed: Future[Built] = Future()
    failed.set_exception(RuntimeError("chunk 2 failed"))
    written = tmp_path / "chunk-3.xml"
    written.write_text("<x/>", encoding="utf-8")
    gone = tmp_path / "chunk-4.xml"
    _parallel._discard_later(
        deque([queued, failed, _built(written), _built(gone)])
    )
    assert queued.cancelled()
    assert not written.exists()
