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

"""Universal data loader supporting multiple input sources."""

from collections.abc import Generator
from typing import Any, Union

# pylint: disable=duplicate-code
from pain001.csv.load_csv_data import load_csv_data, load_csv_data_streaming
from pain001.csv.validate_csv_data import validate_csv_data
from pain001.db.load_db_data import load_db_data
from pain001.db.load_db_data_streaming import load_db_data_streaming
from pain001.db.validate_db_data import validate_db_data
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.json.load_json_data import (
    load_json_data,
    load_json_data_streaming,
    load_jsonl_data,
    load_jsonl_data_streaming,
)
from pain001.parquet.load_parquet_data import (
    load_parquet_data,
    load_parquet_data_streaming,
)


def _get_file_loaders() -> dict[str, tuple[Any, Any, str]]:
    """Build dispatch table at call time so mocks are respected."""
    return {
        ".csv": (load_csv_data, validate_csv_data, "CSV"),
        ".db": (
            lambda p: load_db_data(p, table_name="pain001"),
            validate_db_data,
            "Database",
        ),
        ".json": (load_json_data, validate_csv_data, "JSON"),
        ".jsonl": (load_jsonl_data, validate_csv_data, "JSONL"),
        ".parquet": (load_parquet_data, validate_csv_data, "Parquet"),
    }


def _get_file_stream_loaders() -> dict[str, tuple[Any, Any, str]]:
    """Build streaming dispatch table at call time so mocks are respected."""
    return {
        ".csv": (load_csv_data_streaming, validate_csv_data, "CSV"),
        ".db": (
            lambda p, cs: load_db_data_streaming(p, "pain001", cs),
            validate_db_data,
            "Database",
        ),
        ".json": (load_json_data_streaming, validate_csv_data, "JSON"),
        ".jsonl": (load_jsonl_data_streaming, validate_csv_data, "JSONL"),
        ".parquet": (
            load_parquet_data_streaming,
            validate_csv_data,
            "Parquet",
        ),
    }


def load_payment_data(
    data_source: Union[str, list[dict[str, Any]], dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Universal data loader supporting multiple input sources.

    This function provides a unified interface for loading payment data from
    various sources while maintaining backward compatibility with existing
    file-based workflows.

    Args:
        data_source: The payment data source. Supports:
            - str: File path to CSV (.csv), SQLite (.db), JSON (.json/.jsonl),
                   or Parquet (.parquet) file
            - list: List of dictionaries with payment data
            - dict: Single payment transaction as dictionary

    Returns:
        List[Dict[str, Any]]: List of payment data dictionaries

    Raises:
        ValueError: If data source type is unsupported or data is invalid
        FileNotFoundError: If file path doesn't exist

    Examples:
        # Existing file-based usage (backward compatible)
        >>> data = load_payment_data('payments.csv')
        >>> data = load_payment_data('payments.db')

        # New JSON formats
        >>> data = load_payment_data('payments.json')
        >>> data = load_payment_data('payments.jsonl')  # JSON Lines

        # New Parquet format (requires pyarrow)
        >>> data = load_payment_data('payments.parquet')

        # New direct Python data usage
        >>> data = load_payment_data([
        ...     {'id': 'MSG001', 'amount': '1000.00', ...},
        ...     {'id': 'MSG002', 'amount': '500.00', ...}
        ... ])

        # Single transaction
        >>> data = load_payment_data({
        ...     'id': 'MSG001', 'amount': '1000.00', ...
        ... })
    """
    # pylint: disable=fixme
    # TODO: add streaming/chunked loaders for large CSV/DB sources to reduce memory usage.
    # Handle file path (existing behaviour - backward compatible)
    if isinstance(data_source, str):
        return _load_from_file(data_source)

    # Handle Python dict/list (new feature)
    elif isinstance(data_source, list):
        return _load_from_list(data_source)

    elif isinstance(data_source, dict):
        return _load_from_dict(data_source)

    else:
        raise DataSourceError(
            f"Unsupported data source type: {type(data_source).__name__}. "
            f"Expected str (file path), list, or dict."
        )


def _load_from_file(file_path: str) -> list[dict[str, Any]]:
    """
    Load data from file (CSV, SQLite, JSON, or Parquet).

    This preserves the existing behaviour for backward compatibility.
    and adds support for JSON and Parquet formats.
    """
    import os

    # First, check if file extension is supported (for better error messages)
    supported_extensions = [".csv", ".db", ".json", ".jsonl", ".parquet"]
    if not any(file_path.endswith(ext) for ext in supported_extensions):
        raise DataSourceError(
            f"Unsupported file type: {file_path}. "
            f"Expected .csv, .db, .json, .jsonl, or .parquet file."
        )

    # CodeQL: Prevent path traversal by anchoring to current working directory
    try:
        from pain001.security import validate_path

        base_dir = os.getcwd()
        safe_path = validate_path(
            file_path, must_exist=True, base_dir=base_dir
        )
    except (
        Exception
    ) as e:  # Catch PathValidationError, SecurityError, FileNotFoundError
        raise FileNotFoundError(
            f"Data file validation failed: {file_path}\nError: {e}"
        ) from e

    # Use safe_path for all subsequent operations
    ext = os.path.splitext(safe_path)[1]
    entry = _get_file_loaders().get(ext)
    if entry is None:
        raise DataSourceError(
            f"Unsupported file type: {file_path}. "
            f"Expected .csv, .db, .json, .jsonl, or .parquet file."
        )

    loader_fn, validator_fn, format_name = entry
    data = loader_fn(safe_path)
    if not validator_fn(data):
        raise PaymentValidationError(
            f"{format_name} data validation failed for {file_path}"
        )
    return data


def _load_from_list(data_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Load data from Python list of dictionaries.

    New feature for direct Python data input.
    """
    if not data_list:
        raise DataSourceError("Empty data list provided.")

    if not all(isinstance(item, dict) for item in data_list):
        raise PaymentValidationError(
            "All items in data list must be dictionaries. "
            f"Found: {[type(item).__name__ for item in data_list if not isinstance(item, dict)]}"
        )

    # Mandatory validation for data integrity
    if not validate_csv_data(data_list):
        raise PaymentValidationError("Data list validation failed")
    return data_list


def _load_from_dict(data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Load data from a single Python dictionary.

    New feature for single transaction input.
    """
    if not data_dict:
        raise DataSourceError("Empty data dictionary provided.")

    # Wrap single dict in list and validate
    data_list = [data_dict]
    if not validate_csv_data(data_list):
        raise PaymentValidationError("Data dictionary validation failed")
    return data_list


def load_payment_data_streaming(
    data_source: Union[str, list[dict[str, Any]]],
    chunk_size: int = 1000,
    validate: bool = True,
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

    Yields:
        List[Dict[str, Any]]: Chunks of payment data dictionaries

    Raises:
        ValueError: If data source type is unsupported or data is invalid
        FileNotFoundError: If file path doesn't exist
        DataSourceError: If data source is empty or invalid

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
    # Handle file path (CSV or SQLite)
    if isinstance(data_source, str):
        yield from _load_from_file_streaming(data_source, chunk_size, validate)

    # Handle Python list
    elif isinstance(data_source, list):
        yield from _load_from_list_streaming(data_source, chunk_size, validate)

    else:
        raise DataSourceError(
            f"Unsupported data source type for streaming: {type(data_source).__name__}. "
            f"Expected str (file path) or list. "
            f"For single dict, wrap in list: [your_dict]"
        )


def _load_from_file_streaming(
    file_path: str, chunk_size: int, validate: bool = True
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Stream data from file (CSV, SQLite, JSON, or Parquet) in chunks.

    Memory-efficient for large files.
    """
    import os

    ext = os.path.splitext(file_path)[1]
    entry = _get_file_stream_loaders().get(ext)
    if entry is None:
        raise DataSourceError(
            f"Unsupported file type: {file_path}. "
            f"Expected .csv, .db, .json, .jsonl, or .parquet file."
        )

    stream_loader_fn, validator_fn, format_name = entry
    for chunk in stream_loader_fn(file_path, chunk_size):
        if validate and not validator_fn(chunk):
            raise PaymentValidationError(
                f"{format_name} data validation failed for chunk in {file_path}"
            )
        yield chunk


def _load_from_list_streaming(
    data_list: list[dict[str, Any]], chunk_size: int, validate: bool = True
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
        if validate and not validate_csv_data(chunk):
            raise PaymentValidationError(
                f"Data validation failed for chunk starting at index {i}"
            )
        yield chunk
