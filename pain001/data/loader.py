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

"""Universal data loader supporting multiple input sources."""

import os
from typing import Any

# pylint: disable=duplicate-code
from pain001.csv.load_csv_data import load_csv_data
from pain001.csv.validate_csv_data import row_issues
from pain001.data._checks import _checked, _first_line, _refuse
from pain001.data._streaming import load_payment_data_streaming
from pain001.db.load_db_data import load_db_data
from pain001.db.validate_db_data import db_row_issues
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.json.load_json_data import load_json_data, load_jsonl_data
from pain001.parquet.load_parquet_data import load_parquet_data

__all__ = ["load_payment_data", "load_payment_data_streaming"]


def _get_file_loaders() -> dict[str, tuple[Any, Any, str]]:
    """Build dispatch table at call time so mocks are respected."""
    return {
        ".csv": (load_csv_data, row_issues, "CSV"),
        ".db": (
            lambda p: load_db_data(p, table_name="pain001"),
            db_row_issues,
            "Database",
        ),
        ".json": (load_json_data, row_issues, "JSON"),
        ".jsonl": (load_jsonl_data, row_issues, "JSONL"),
        ".parquet": (load_parquet_data, row_issues, "Parquet"),
    }


def _require_valid(
    rows: list[dict[str, Any]], file_path: str, message_type: str | None
) -> None:
    """Run the built-in post-load check for ``file_path``'s type.

    Args:
        rows: The loaded rows.
        file_path: The file they came from.
        message_type: The type whose columns each row must carry.
    """
    ext = os.path.splitext(file_path)[1].lower()
    entry = _get_file_loaders().get(ext)
    if entry is not None:
        _, issues_for, format_name = entry
        issues = issues_for(
            rows, message_type, first_line=_first_line(file_path)
        )
        _refuse(
            f"{format_name} data validation failed for {file_path}", issues
        )


def load_payment_data(
    data_source: str | list[dict[str, Any]] | dict[str, Any],
    identifier_checks: bool = True,
    message_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Universal data loader supporting multiple input sources.

    This function provides a unified interface for loading payment data from
    various sources while maintaining backward compatibility with existing
    file-based workflows.

    Args:
        data_source: File path to CSV, SQLite, JSON, JSONL, Parquet or a
            registered plugin format; a list of payment dictionaries; or
            one payment transaction dictionary.
        identifier_checks: Check every IBAN (mod-97, country length),
            BIC (ISO 9362) and LEI (ISO 17442) column; False skips
            those checks.
        message_type: The target message type: every row must carry
            the columns its schema requires. ``None`` (the type is not
            known) requires every column all bundled schemas describe.

    Returns:
        List[Dict[str, Any]]: List of payment data dictionaries

    A DataSourceError for an unsupported source type, and errors from
    the underlying loaders (e.g. FileNotFoundError for missing files,
    PaymentValidationError for invalid rows or identifiers), propagate
    unchanged.

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
    return _checked(
        _load_any(data_source, message_type),
        identifier_checks,
        first_line=_first_line(data_source),
    )


def _load_any(
    data_source: str | list[dict[str, Any]] | dict[str, Any],
    message_type: str | None = None,
) -> list[dict[str, Any]]:
    """Dispatch ``data_source`` to the loader for its type.

    Args:
        data_source: A file path, a list of rows or one row.
        message_type: The type whose columns each row must carry.

    Returns:
        The loaded rows.

    Raises:
        DataSourceError: If the data source type is unsupported.
    """
    # pylint: disable=fixme
    # TODO: add streaming/chunked loaders for large CSV/DB sources to reduce memory usage.
    # Handle file path (existing behaviour - backward compatible)
    if isinstance(data_source, str):
        return _load_from_file(data_source, message_type)

    # Handle Python dict/list (new feature)
    elif isinstance(data_source, list):
        return _load_from_list(data_source, message_type)

    elif isinstance(data_source, dict):
        return _load_from_dict(data_source, message_type)

    else:
        raise DataSourceError(
            f"Unsupported data source type: {type(data_source).__name__}. "
            f"Expected str (file path), list, or dict."
        )


def _load_from_file(
    file_path: str, message_type: str | None = None
) -> list[dict[str, Any]]:
    """
    Load data from file (CSV, SQLite, JSON, Parquet, or a plugin-registered format).

    Extensions in the built-in dispatch table (`.csv`, `.db`,
    `.json`, `.jsonl`, `.parquet`) keep their existing post-load
    validator. Anything else falls through to the v0.0.54 plugin
    registry so an installed third-party loader
    (`pain001-loader-xlsx`, `pain001-loader-gpg`, ...) handles the
    file. Plugin-handled formats own their own validation.
    """
    from pain001.plugins.registry import registry as plugin_registry

    # Early extension check (fast-fail before path validation). The
    # supported set is the union of the built-in dispatch table and any
    # extension a plugin has registered for - so installing
    # `pain001-loader-xlsx` makes `.xlsx` immediately accepted here.
    ext = os.path.splitext(file_path)[1].lower()
    plugin_loader = plugin_registry.get_loader_for_extension(ext)
    if plugin_loader is None:
        from pain001.plugins.companions import install_hint

        hint = install_hint(ext)
        if hint:
            # A first-party package handles this format. Naming it is
            # the difference between an error the user can act on and
            # one that sends them to the issue tracker.
            raise DataSourceError(
                f"No loader registered for {ext}; install {hint} "
                f"(file: {file_path})."
            )
        raise DataSourceError(
            f"Unsupported file type: {file_path}. "
            f"Expected .csv, .db, .json, .jsonl, or .parquet file, or "
            f"install a plugin that registers the {ext!r} extension "
            f"(see `pain001 plugins list`)."
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

    # Every loader uses the contract; retain the built-in post-load gate.
    data = plugin_loader.load(safe_path).rows
    _require_valid(data, file_path, message_type)
    return data


def _load_from_list(
    data_list: list[dict[str, Any]], message_type: str | None = None
) -> list[dict[str, Any]]:
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
    _refuse("Data list validation failed", row_issues(data_list, message_type))
    return data_list


def _load_from_dict(
    data_dict: dict[str, Any], message_type: str | None = None
) -> list[dict[str, Any]]:
    """
    Load data from a single Python dictionary.

    New feature for single transaction input.
    """
    if not data_dict:
        raise DataSourceError("Empty data dictionary provided.")

    # Wrap single dict in list and validate
    data_list = [data_dict]
    _refuse(
        "Data dictionary validation failed",
        row_issues(data_list, message_type),
    )
    return data_list
