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

"""Small helpers ``pain001.core.core`` uses to describe a generation."""

from typing import Any

from pain001.observability import set_span_attributes


def determine_data_source_type(
    data_file_path: str | list[dict[str, Any]] | dict[str, Any],
) -> str:
    """Determine the type of the data source.

    Args:
        data_file_path: A file path, a list of rows or one row.

    Returns:
        The source kind used in logs and metrics (``csv``, ``list`` ...).
    """
    if isinstance(data_file_path, list):
        return "list"
    if isinstance(data_file_path, dict):
        return "dict"
    if not isinstance(data_file_path, str):
        return "unknown"

    if data_file_path.endswith(".db") or "sqlite" in data_file_path:
        return "sqlite"

    for ext in [".csv", ".jsonl", ".json", ".parquet"]:
        if data_file_path.endswith(ext):
            return ext.lstrip(".")

    return "file"


def stamp_span(message_type: str, row_count: int) -> None:
    """Record the message type and row count on the active span.

    Args:
        message_type: The ISO 20022 message type being generated.
        row_count: Number of payment rows loaded.
    """
    # Stamp the active OTel span (a no-op when OTEL_ENABLED is
    # unset) so operators can pivot traces by message type +
    # row count.
    set_span_attributes(
        **{
            "pain001.message_type": message_type,
            "pain001.row_count": row_count,
        }
    )
