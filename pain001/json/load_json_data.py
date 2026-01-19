# Copyright (C) 2023-2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""JSON data loader for payment data."""

# pylint: disable=duplicate-code
import json
import logging
import os
from collections.abc import Generator
from typing import Any

from pain001.exceptions import DataSourceError
from pain001.security import validate_path

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")


def load_json_data(file_path: str) -> list[dict[str, Any]]:
    """Load payment data from JSON file.

    Supports both single object and array of objects format.

    Args:
        file_path: Path to JSON file containing payment data.

    Returns:
        List of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If JSON is invalid or empty.
        json.JSONDecodeError: If JSON is malformed.

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
    if not os.path.isfile(safe_path):
        raise FileNotFoundError(f"JSON file not found: {file_path}")

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

    Yields:
        Chunks of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If JSON is invalid or empty.

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
        DataSourceError: If JSONL is invalid.

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
    if not os.path.isfile(file_path_validated):
        raise FileNotFoundError(f"JSONL file not found: {file_path}")

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
        if isinstance(e, DataSourceError):
            raise
        raise DataSourceError(
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
        Chunks of payment data dictionaries.

    Raises:
        FileNotFoundError: If file doesn't exist.
        DataSourceError: If JSONL is invalid.

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
    if not os.path.isfile(file_path_validated):
        raise FileNotFoundError(f"JSONL file not found: {file_path}")

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
        if isinstance(e, DataSourceError):
            raise
        raise DataSourceError(
            f"Error reading JSONL file {file_path}: {e}"
        ) from e
