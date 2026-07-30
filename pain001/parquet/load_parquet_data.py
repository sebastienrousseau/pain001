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

"""Parquet data loader for payment data (optional feature)."""

# pylint: disable=duplicate-code
import os
from collections.abc import Generator
from typing import Any, cast

from pain001.exceptions import DataSourceError
from pain001.security import validate_path

# Optional import: pyarrow is not a required dependency
try:
    import pyarrow.parquet as pq  # type: ignore[import-untyped,import-not-found,unused-ignore]

    HAS_PARQUET_SUPPORT = True
except ImportError:  # pragma: no cover
    HAS_PARQUET_SUPPORT = False


def _check_parquet_support() -> None:
    """Check if pyarrow is installed for Parquet support.

    Raises:
        DataSourceError: If pyarrow is not installed.
    """
    if not HAS_PARQUET_SUPPORT:  # pragma: no cover
        raise DataSourceError(  # pragma: no cover
            "Parquet support requires pyarrow. Install with: pip install pyarrow"
        )


def load_parquet_data(file_path: str) -> list[dict[str, Any]]:
    """Load payment data from Parquet file.

    Parquet is a columnar storage format optimized for analytics workloads.
    It provides excellent compression and fast read performance for large datasets.

    Args:
        file_path: Path to Parquet file containing payment data.

    Returns:
        List of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If pyarrow is not installed or the file is
            invalid or empty.
        Exception: A FileNotFoundError or DataSourceError raised inside
            the read block is re-raised unchanged via a bare ``raise``.

    Examples:
        >>> data = load_parquet_data('payments.parquet')
        # [{'id': 'MSG001', 'amount': '1000.00', ...}, ...]

    Note:
        Requires pyarrow: pip install pyarrow
    """
    _check_parquet_support()

    # Validate path to prevent traversal attacks

    try:
        safe_path = validate_path(file_path)  # nosec B108 - Returns sanitized string
    except Exception as e:  # pragma: no cover
        raise FileNotFoundError(  # pragma: no cover
            f"Parquet file path validation failed: {file_path}"
        ) from e

    # Check file existence using os.path for string path
    if not os.path.isfile(safe_path):
        raise FileNotFoundError(f"Parquet file not found: {file_path}")

    try:
        # Read Parquet file (now safe after validation)
        table = pq.read_table(str(safe_path))  # nosec B108

        # Convert to list of dicts
        data = cast(list[dict[str, Any]], table.to_pylist())

        if not data:
            raise DataSourceError(f"Parquet file is empty: {file_path}")

        return data

    except Exception as e:
        if isinstance(e, (FileNotFoundError, DataSourceError)):
            raise
        raise DataSourceError(
            f"Error reading Parquet file {file_path}: {e}"
        ) from e


def load_parquet_data_streaming(
    file_path: str, chunk_size: int = 1000
) -> Generator[list[dict[str, Any]], None, None]:
    """Load Parquet data in chunks for memory efficiency.

    Uses pyarrow's batch reader for true streaming without loading
    the entire file into memory.

    Args:
        file_path: Path to Parquet file.
        chunk_size: Number of records per chunk (default: 1000).

    Yields:
        list[dict[str, Any]]: Chunks of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If pyarrow is not installed or the file is
            invalid.
        Exception: A FileNotFoundError or DataSourceError raised inside
            the read block is re-raised unchanged via a bare ``raise``.

    Examples:
        >>> for chunk in load_parquet_data_streaming('large_payments.parquet'):
        ...     process_batch(chunk)

    Note:
        Requires pyarrow: pip install pyarrow
    """
    _check_parquet_support()

    # Validate path to prevent traversal attacks
    try:
        safe_path = validate_path(file_path)  # nosec B108
    except Exception as e:  # pragma: no cover
        raise FileNotFoundError(  # pragma: no cover
            f"Parquet file path validation failed: {file_path}"
        ) from e

    if not os.path.isfile(safe_path):
        raise FileNotFoundError(f"Parquet file not found: {file_path}")

    try:
        # Open Parquet file for streaming
        parquet_file = pq.ParquetFile(str(safe_path))

        # Read in batches
        for batch in parquet_file.iter_batches(batch_size=chunk_size):
            # Convert batch to list of dicts
            chunk_data = cast(list[dict[str, Any]], batch.to_pylist())
            if chunk_data:  # pragma: no cover
                yield chunk_data

    except Exception as e:
        if isinstance(
            e, (FileNotFoundError, DataSourceError)
        ):  # pragma: no cover
            raise  # pragma: no cover
        raise DataSourceError(
            f"Error reading Parquet file {file_path}: {e}"
        ) from e
