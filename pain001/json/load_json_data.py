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

"""JSON data loader for payment data."""

# pylint: disable=duplicate-code
import json
import os
from collections.abc import Generator
from typing import Any

from pain001.exceptions import DataSourceError
from pain001.security import validate_path


def load_json_data(file_path: str) -> list[dict[str, Any]]:
    """Load payment data from JSON file.

    Supports both single object and array of objects format.

    Args:
        file_path: Path to JSON file containing payment data.

    Returns:
        List of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If JSON is malformed, empty, or not an
            object/array.

    Examples:
        # Array format (preferred)
        >>> data = load_json_data('payments.json')
        # [{'id': 'MSG001', 'amount': '1000.00', ...}, ...]

        # Single object format
        >>> data = load_json_data('payment.json')
        # Automatically wrapped: [{'id': 'MSG001', ...}]
    """
    # Validate path to prevent traversal attacks

    try:
        # Restrict JSON file access to the current working directory by default.
        base_dir = os.getcwd()
        safe_path = validate_path(
            file_path,
            must_exist=True,
            base_dir=base_dir,
        )  # nosec B108 - Returns sanitized, normalized string
    except Exception as e:
        # Fail securely - do not fall back to unsafe path
        raise FileNotFoundError(
            f"JSON file not found or invalid path: {file_path}"
        ) from e

    # Check file existence using os.path for string path
    if not os.path.isfile(safe_path):  # pragma: no cover
        raise FileNotFoundError(
            f"JSON file not found: {file_path}"
        )  # pragma: no cover

    try:
        with open(safe_path, encoding="utf-8") as f:  # nosec B108
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise DataSourceError(f"Invalid JSON: {e}") from e

    # Handle both single object and array formats
    if isinstance(data, dict):
        # Single payment object - wrap in list
        return [data]
    elif isinstance(data, list):
        # Array of payments - validate all are dicts
        if not all(isinstance(item, dict) for item in data):
            non_dict_types = {
                type(item).__name__
                for item in data
                if not isinstance(item, dict)
            }
            raise DataSourceError(
                f"JSON array must contain only objects (dictionaries). "
                f"Found: {non_dict_types}"
            )
        return data
    else:
        raise DataSourceError(
            f"JSON file must contain an object or array. "
            f"Found: {type(data).__name__}"
        )


def load_json_data_streaming(
    file_path: str, chunk_size: int = 1000
) -> Generator[list[dict[str, Any]], None, None]:
    """Load JSON data in chunks for memory efficiency.

    Note: This loads the entire JSON file into memory first, then yields chunks.
    JSON doesn't support true streaming due to its structure. For large JSON files,
    consider converting to JSONL (JSON Lines) format or use Parquet.

    Args:
        file_path: Path to JSON file.
        chunk_size: Number of records per chunk (default: 1000).

    Errors from load_json_data (FileNotFoundError, DataSourceError)
    propagate unchanged.

    Yields:
        list[dict[str, Any]]: Chunks of payment data dictionaries.

    Examples:
        >>> for chunk in load_json_data_streaming('payments.json', chunk_size=500):
        ...     process_batch(chunk)
    """
    # Load all data (JSON doesn't support true streaming)
    data = load_json_data(file_path)

    # Yield in chunks
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def load_jsonl_data(file_path: str) -> list[dict[str, Any]]:
    """Load payment data from JSON Lines (.jsonl) file.

    JSON Lines format has one JSON object per line, enabling true streaming
    for large datasets.

    Args:
        file_path: Path to JSONL file.

    Returns:
        List of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If the JSONL is invalid or empty.
        Exception: A DataSourceError raised inside the read loop is
            re-raised unchanged via a bare ``raise``.

    Examples:
        >>> data = load_jsonl_data('payments.jsonl')
    """
    try:
        # Restrict JSONL file access to the current working directory by default.
        base_dir = os.getcwd()
        file_path_validated = validate_path(
            file_path,
            must_exist=True,
            base_dir=base_dir,
        )  # nosec B108 - Returns sanitized string
    except Exception as e:
        raise FileNotFoundError(
            f"JSONL file not found or invalid path: {file_path}"
        ) from e

    # Check file existence using os.path for string path
    if not os.path.isfile(file_path_validated):  # pragma: no cover
        raise FileNotFoundError(
            f"JSONL file not found: {file_path}"
        )  # pragma: no cover

    data = []
    try:
        with open(file_path_validated, encoding="utf-8") as f:  # nosec B108
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines

                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise DataSourceError(
                            f"Line {line_num}: Expected JSON object, got {type(item).__name__}"
                        )
                    data.append(item)
                except json.JSONDecodeError as e:
                    raise DataSourceError(
                        f"Invalid JSON on line {line_num}: {e}"
                    ) from e

    except Exception as e:
        if isinstance(e, DataSourceError):  # pragma: no cover
            raise
        raise DataSourceError(  # pragma: no cover
            f"Error reading JSONL file {file_path}: {e}"
        ) from e

    if not data:
        raise DataSourceError(f"JSONL file is empty: {file_path}")

    return data


def load_jsonl_data_streaming(
    file_path: str, chunk_size: int = 1000
) -> Generator[list[dict[str, Any]], None, None]:
    """Load JSONL data in true streaming fashion.

    This is the preferred method for large JSON datasets as it doesn't load
    the entire file into memory.

    Args:
        file_path: Path to JSONL file.
        chunk_size: Number of records per chunk (default: 1000).

    Yields:
        list[dict[str, Any]]: Chunks of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If the JSONL is invalid.
        Exception: A DataSourceError raised inside the read loop is
            re-raised unchanged via a bare ``raise``.

    Examples:
        >>> for chunk in load_jsonl_data_streaming('large_payments.jsonl'):
        ...     process_batch(chunk)
    """
    try:
        base_dir = os.getcwd()
        file_path_validated = validate_path(
            file_path,
            must_exist=True,
            base_dir=base_dir,
        )  # nosec B108 - Returns sanitized string
    except Exception as e:
        raise FileNotFoundError(
            f"JSONL file not found or invalid path: {file_path}"
        ) from e

    # Check file existence using os.path for string path
    if not os.path.isfile(file_path_validated):  # pragma: no cover
        raise FileNotFoundError(
            f"JSONL file not found: {file_path}"
        )  # pragma: no cover

    chunk: list[dict[str, Any]] = []

    try:
        with open(file_path_validated, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines

                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise DataSourceError(
                            f"Line {line_num}: Expected JSON object, got {type(item).__name__}"
                        )

                    chunk.append(item)

                    # Yield chunk when full
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []

                except json.JSONDecodeError as e:
                    raise DataSourceError(
                        f"Invalid JSON on line {line_num}: {e}"
                    ) from e

        # Yield remaining items
        if chunk:
            yield chunk

    except Exception as e:
        if isinstance(e, DataSourceError):  # pragma: no cover
            raise
        raise DataSourceError(  # pragma: no cover
            f"Error reading JSONL file {file_path}: {e}"
        ) from e
