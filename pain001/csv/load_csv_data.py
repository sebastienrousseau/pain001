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

import csv
import logging
import os
from collections.abc import Generator
from typing import Any

from pain001.exceptions import DataSourceError
from pain001.security import sanitize_for_log, validate_path  # noqa: PYI100

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")


def load_csv_data(file_path: str) -> list[dict[str, Any]]:
    """Load CSV data from a file.

    Args:
        file_path (str): The path to the CSV file.

    Returns:
        list: A list of dictionaries containing the CSV data.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If there is an issue reading the file.
        UnicodeDecodeError: If there is an issue decoding the file's content.
        ValueError: If the CSV file is empty.

    Note:
        For large files, consider using load_csv_data_streaming() to reduce
        memory footprint.
    """
    # Validate path to prevent traversal attacks

    # Pre-validate file path (CodeQL: prevent path traversal)
    try:
        # Restrict CSV file access to the current working directory by default.
        base_dir = os.getcwd()
        safe_path = validate_path(
            file_path,
            must_exist=True,
            base_dir=base_dir,
        )  # nosec B108 - Returns sanitized string
    except Exception as e:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(
            f"Path validation failed: {sanitize_for_log(str(file_path))} - {e}"
        )
        raise

    # Check file existence using os.path for string path
    if not os.path.isfile(safe_path):
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(f"File not found: {sanitize_for_log(str(file_path))}")
        raise FileNotFoundError(
            f"File '{sanitize_for_log(str(file_path))}' not found."
        )

    data: list[dict[str, Any]] = []
    try:
        with open(safe_path, encoding="utf-8") as file:  # nosec B108
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                data.append(row)
    except OSError:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(
            f"IOError reading file: {sanitize_for_log(str(file_path))}"
        )
        raise
    except UnicodeDecodeError:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(
            f"UnicodeDecodeError decoding file: {sanitize_for_log(str(file_path))}"
        )
        raise

    if not data:
        raise DataSourceError(f"The CSV file '{file_path}' is empty.")

    return data


def load_csv_data_streaming(
    file_path: str, chunk_size: int = 1000
) -> Generator[list[dict[str, Any]], None, None]:
    """Load CSV data from a file in chunks for memory-efficient processing.

    This function yields chunks of CSV data instead of loading the entire
    file into memory, making it suitable for large files.

    Args:
        file_path (str): The path to the CSV file.
        chunk_size (int): Number of rows to yield per chunk. Default is 1000.

    Yields:
        list: A list of dictionaries containing chunk_size rows of CSV data.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If there is an issue reading the file.
        UnicodeDecodeError: If there is an issue decoding the file's content.
        ValueError: If the CSV file is empty.

    Example:
        >>> for chunk in load_csv_data_streaming('large_file.csv', chunk_size=500):
        ...     # Process chunk
        ...     process_payment_batch(chunk)

    Performance:
        - Memory usage: ~90% reduction for large files (10K+ rows)
        - Enables processing of files larger than available RAM
        - Slightly slower than load_csv_data() due to yielding overhead
    """
    chunk: list[dict[str, Any]] = []
    row_count = 0

    try:
        # CodeQL: Prevent path traversal
        base_dir = os.getcwd()
        safe_path = validate_path(
            file_path,
            must_exist=True,
            base_dir=base_dir,
        )  # nosec B108
    except Exception as e:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(
            f"Path validation failed: {sanitize_for_log(str(file_path))} - {e}"
        )
        raise

    try:
        with open(safe_path, encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                chunk.append(row)
                row_count += 1
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []

            # Yield remaining rows
            if chunk:
                yield chunk

    except FileNotFoundError:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(f"File '{sanitize_for_log(str(file_path))}' not found.")
        raise
    except OSError:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(
            f"An IOError occurred while reading the file '{sanitize_for_log(str(file_path))}'."
        )
        raise
    except UnicodeDecodeError:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        logging.error(
            f"A UnicodeDecodeError occurred while decoding the file '{sanitize_for_log(str(file_path))}'."
        )
        raise

    if row_count == 0:
        # Sanitize at sink (CWE-117: Log Injection prevention)
        raise DataSourceError(
            f"The CSV file '{sanitize_for_log(str(file_path))}' is empty."
        )
