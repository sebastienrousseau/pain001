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

"""Stream payment rows in chunks, each checked like a whole input.

Split from :mod:`pain001.data.loader`, which re-exports
:func:`load_payment_data_streaming`.
"""

import os
from collections.abc import Generator, Iterable
from typing import Any

# pylint: disable=duplicate-code
from pain001.csv.load_csv_data import load_csv_data_streaming
from pain001.csv.validate_csv_data import row_issues
from pain001.data._checks import _checked, _first_line, _refuse
from pain001.db.load_db_data_streaming import load_db_data_streaming
from pain001.db.validate_db_data import db_row_issues
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.json.load_json_data import (
    load_json_data_streaming,
    load_jsonl_data_streaming,
)
from pain001.parquet.load_parquet_data import load_parquet_data_streaming

__all__ = ["load_payment_data_streaming"]


def _get_file_stream_loaders() -> dict[str, tuple[Any, Any, str]]:
    """Build streaming dispatch table at call time so mocks are respected."""
    return {
        ".csv": (load_csv_data_streaming, row_issues, "CSV"),
        ".db": (
            lambda p, cs: load_db_data_streaming(p, "pain001", cs),
            db_row_issues,
            "Database",
        ),
        ".json": (load_json_data_streaming, row_issues, "JSON"),
        ".jsonl": (load_jsonl_data_streaming, row_issues, "JSONL"),
        ".parquet": (
            load_parquet_data_streaming,
            row_issues,
            "Parquet",
        ),
    }


def load_payment_data_streaming(
    data_source: str | list[dict[str, Any]],
    chunk_size: int = 1000,
    validate: bool = True,
    identifier_checks: bool = True,
    message_type: str | None = None,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Memory-efficient streaming loader supporting multiple input sources.

    This function yields chunks of payment data instead of loading everything
    into memory, making it suitable for large datasets (millions of rows).

    Args:
        data_source: The payment data source. Supports:
            - str: File path to CSV (.csv) or SQLite (.db) file
            - list: List of dictionaries with payment data
        chunk_size: Number of records to yield per chunk. Default is 1000.
        validate: If True, validate each chunk. Default True.
                 Set False for testing or when data is pre-validated.
        identifier_checks: Check each chunk's IBAN and BIC columns,
            whatever ``validate`` says; False skips those checks.
        message_type: The type whose required columns each chunk must
            carry; ``None`` requires every column any schema describes.

    Yields:
        list[dict[str, Any]]: Chunks of payment data dictionaries

    A DataSourceError for an unsupported source type, and errors from
    the underlying streaming loaders (e.g. FileNotFoundError for missing
    files, PaymentValidationError for a chunk that fails validation or
    carries an invalid IBAN or BIC), propagate unchanged.

    Examples:
        # Streaming from large CSV file
        >>> for chunk in load_payment_data_streaming('large_payments.csv', chunk_size=500):
        ...     process_batch(chunk)

        # Streaming from large SQLite database
        >>> for chunk in load_payment_data_streaming('payments.db', chunk_size=1000):
        ...     generate_xml_batch(chunk)

        # Streaming from large Python list (useful for APIs)
        >>> large_data = [{'id': f'TX{i}', ...} for i in range(100000)]
        >>> for chunk in load_payment_data_streaming(large_data, chunk_size=500):
        ...     validate_and_process(chunk)

    Performance:
        - Memory usage: O(chunk_size) instead of O(total_records)
        - Enables processing datasets larger than available RAM
        - ~10-15% slower than load_payment_data() due to yielding overhead
        - Best for files/datasets with 10,000+ records

    Note:
        Single dict input not supported in streaming mode. Convert to list first.
    """
    chunks = _stream_any(data_source, chunk_size, validate, message_type)
    first_line = _first_line(data_source)
    yield from _identifiers_checked(chunks, identifier_checks, first_line)


def _identifiers_checked(
    chunks: Iterable[list[dict[str, Any]]],
    identifier_checks: bool,
    first_line: int,
) -> Generator[list[dict[str, Any]], None, None]:
    """Yield each chunk once its identifiers pass, if asked.

    Args:
        chunks: The chunks, in input order.
        identifier_checks: False yields them unchecked.
        first_line: The line of the input's first row.

    Yields:
        list[dict[str, Any]]: Each chunk, unchanged.
    """
    start = 0
    for chunk in chunks:
        yield _checked(chunk, identifier_checks, start, first_line)
        start += len(chunk)


def _stream_any(
    data_source: str | list[dict[str, Any]],
    chunk_size: int,
    validate: bool,
    message_type: str | None = None,
) -> Generator[list[dict[str, Any]], None, None]:
    """Dispatch ``data_source`` to the streaming loader for its type.

    Args:
        data_source: A file path or a list of rows.
        chunk_size: Number of records per chunk.
        validate: If True, validate each chunk.
        message_type: The type whose columns each chunk must carry, or
            ``None`` for every column.

    Yields:
        list[dict[str, Any]]: Chunks of payment rows.

    Raises:
        DataSourceError: If the data source type is unsupported.
    """
    # Handle file path (CSV or SQLite)
    if isinstance(data_source, str):
        yield from _load_from_file_streaming(
            data_source, chunk_size, validate, message_type
        )

    # Handle Python list
    elif isinstance(data_source, list):
        yield from _load_from_list_streaming(
            data_source, chunk_size, validate, message_type
        )

    else:
        raise DataSourceError(
            f"Unsupported data source type for streaming: {type(data_source).__name__}. "
            f"Expected str (file path) or list. "
            f"For single dict, wrap in list: [your_dict]"
        )


def _load_from_file_streaming(
    file_path: str,
    chunk_size: int,
    validate: bool = True,
    message_type: str | None = None,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Stream data from file (CSV, SQLite, JSON, or Parquet) in chunks.

    Memory-efficient for large files.
    """
    from pain001.plugins.registry import registry as plugin_registry

    ext = os.path.splitext(file_path)[1].lower()
    plugin_loader = plugin_registry.get_loader_for_extension(ext)
    entry = _get_file_stream_loaders().get(ext)
    if plugin_loader is None:
        raise DataSourceError(
            f"Unsupported file type: {file_path}. "
            f"Expected .csv, .db, .json, .jsonl, or .parquet file."
        )

    start = 0
    first_line = _first_line(file_path)
    for result in plugin_loader.load_streaming(file_path, chunk_size):
        chunk = result.rows
        if validate and entry is not None:
            issues = entry[1](
                chunk, message_type, first_line=first_line + start
            )
            _refuse(
                f"{entry[2]} data validation failed for chunk in {file_path}",
                issues,
            )
        start += len(chunk)
        yield chunk


def _load_from_list_streaming(
    data_list: list[dict[str, Any]],
    chunk_size: int,
    validate: bool = True,
    message_type: str | None = None,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Stream data from Python list in chunks.

    Useful for API inputs or in-memory data processing.
    """
    if not data_list:
        raise DataSourceError("Empty data list provided.")

    if not all(isinstance(item, dict) for item in data_list):
        raise PaymentValidationError(
            "All items in data list must be dictionaries. "
            f"Found: {[type(item).__name__ for item in data_list if not isinstance(item, dict)]}"
        )

    # Yield data in chunks
    for i in range(0, len(data_list), chunk_size):
        chunk = data_list[i : i + chunk_size]
        if validate:
            _refuse(
                f"Data validation failed for chunk starting at index {i}",
                row_issues(chunk, message_type, first_line=1 + i),
            )
        yield chunk
