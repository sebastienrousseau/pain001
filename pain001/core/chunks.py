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

"""One distinct message per streamed chunk.

``process_files_streaming`` writes one file per chunk, and each file is
a message of its own. Its GrpHdr/MsgId (and its PmtInfId, when the rows
name one) comes from the chunk's first row, so a batch-level id would
repeat across the files of one run and a bank would reject every file
after the first as a duplicate. When a run has more than one chunk,
chunk ``n`` (1-based) therefore carries ``<id>-<n>`` and
``<payment_information_id>-<n>``, cut to the schemas' ``Max35Text`` by
shortening the base, never the suffix. A run that fits one chunk is the
whole message and keeps its ids, so its file is byte-identical to the
one ``process_files`` writes.
"""

from collections.abc import Iterable, Iterator
from itertools import chain
from typing import Any

#: Every bundled schema types MsgId and PmtInfId as Max35Text.
MAX_ID_LENGTH = 35

#: The columns that become GrpHdr/MsgId and PmtInf/PmtInfId.
_ID_COLUMNS = ("id", "payment_information_id")

Rows = list[dict[str, Any]]


def chunk_identifier(base: str, index: int) -> str:
    """``<base>-<index>``, the base cut so the whole fits Max35Text.

    Args:
        base: The identifier the chunk's rows carry.
        index: The 1-based chunk number.

    Returns:
        The chunk's identifier; a blank base is returned unchanged, so
        a column the rows leave empty stays empty.
    """
    if not base.strip():
        return base
    suffix = f"-{index}"
    return base[: MAX_ID_LENGTH - len(suffix)] + suffix


def _renumbered(rows: Rows, index: int) -> Rows:
    """Copies of ``rows`` carrying chunk ``index``'s identifiers."""
    head = rows[0]
    ids = {
        column: chunk_identifier(str(head[column]), index)
        for column in _ID_COLUMNS
        if head.get(column) is not None
    }
    return [{**row, **ids} for row in rows]


def numbered_chunks(chunks: Iterable[Rows]) -> Iterator[tuple[int, Rows]]:
    """Number the chunks and give each its own message identifiers.

    Reads one chunk ahead to learn whether the run has more than one:
    a single chunk is yielded untouched.

    Args:
        chunks: The rows of each chunk, in order.

    Yields:
        tuple[int, Rows]: ``(n, rows)`` with ``n`` 1-based.
    """
    iterator = iter(chunks)
    first = next(iterator, None)
    if first is None:
        return
    second = next(iterator, None)
    if second is None:
        yield 1, first
        return
    for index, rows in enumerate(chain((first, second), iterator), 1):
        yield index, _renumbered(rows, index)
