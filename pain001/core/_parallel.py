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

"""Build streamed chunks one after another, or in worker processes.

A streamed run writes one file per chunk, and chunks do not depend on
each other, so ``workers > 1`` builds them in separate processes:
rendering and XSD validation are pure Python and hold the GIL, so
threads would not help. Workers start with ``spawn`` on every platform
(no inherited locks or threads), and at most twice as many chunks as
workers are in flight, so memory stays bounded.

Results come back in chunk order, and a failure keeps the sequential
guarantee: the failing chunk is never written, earlier chunks stay
published, and a later chunk a worker had already published is
removed before the error propagates.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import os
from collections import deque
from collections.abc import Iterable, Iterator
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

#: A built chunk: its 1-based index, its published path, its row count.
Built = tuple[int, str, int]


@dataclass(frozen=True)
class ChunkJob:
    """Everything one chunk needs, picklable for a worker process."""

    index: int
    rows: list[dict[str, Any]]
    message_type: str
    template: str
    schema: str
    output_dir: str
    envelop_bah: bool = False
    bah_header: Any = None
    sign_key: str | bytes | None = None
    sign_cert: str | bytes | None = None
    sign_passphrase: str | bytes | None = None
    schematron: Any = None


def chunk_output_path(base_xml_path: str, chunk_index: int) -> str:
    """Build a chunk-specific XML output path."""
    stem, suffix = os.path.splitext(base_xml_path)
    return f"{stem}.chunk{chunk_index:04d}{suffix}"


def build_chunk(job: ChunkJob) -> Built:
    """Render, finalise, check and publish one chunk.

    Args:
        job: The chunk and how to build it.

    Returns:
        The chunk's index, published path and row count.
    """
    from pain001.xml import generate_xml as xml_generate
    from pain001.xml.publish import (
        finalise_message,
        publish_text,
        require_schematron,
    )
    from pain001.xml.register_namespaces import register_namespaces

    # A spawned worker starts with no namespaces registered.
    register_namespaces(job.message_type)
    xml_content = xml_generate.generate_xml_string(
        job.rows, job.message_type, job.template, job.schema
    )
    xml_content = finalise_message(
        xml_content,
        job.envelop_bah,
        job.bah_header,
        job.sign_key,
        job.sign_cert,
        job.sign_passphrase,
    )
    path = chunk_output_path(
        os.path.join(job.output_dir, f"{job.message_type}.xml"), job.index
    )
    # Schematron runs on the final bytes; publish_text stages, fsyncs and
    # renames, so a refused or failed chunk never appears.
    if job.schematron is not None:
        require_schematron(
            xml_content,
            job.schematron,
            f"Schematron validation failed for chunk '{path}'",
        )
    publish_text(xml_content, path)
    return job.index, path, len(job.rows)


def _discard_later(pending: deque[Future[Built]]) -> None:
    """Cancel or wait for the chunks after a failure; unlink any published."""
    for future in pending:
        future.cancel()
    for future in pending:
        if future.cancelled() or future.exception() is not None:
            continue
        with contextlib.suppress(FileNotFoundError):
            os.unlink(future.result()[1])


def build_chunks(
    jobs: Iterable[ChunkJob], workers: int = 1
) -> Iterator[Built]:
    """Build every chunk, in order, with ``workers`` processes.

    Args:
        jobs: The chunks, in order.
        workers: Worker processes; 1 builds in this process.

    Yields:
        Built: Each chunk's index, path and row count, in chunk order.

    Raises:
        ValueError: If ``workers`` is less than 1.
        BaseException: Whatever building a chunk raised, re-raised once
            the later chunks are cancelled or removed.
    """
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if workers == 1:
        for job in jobs:
            yield build_chunk(job)
        return
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        pending: deque[Future[Built]] = deque()
        source = iter(jobs)
        for job in source:
            pending.append(pool.submit(build_chunk, job))
            if len(pending) >= 2 * workers:
                break
        while pending:
            future = pending.popleft()
            try:
                built = future.result()
            except BaseException:
                _discard_later(pending)
                raise
            next_job = next(source, None)
            if next_job is not None:
                pending.append(pool.submit(build_chunk, next_job))
            yield built


__all__ = [
    "Built",
    "ChunkJob",
    "build_chunk",
    "build_chunks",
    "chunk_output_path",
]
