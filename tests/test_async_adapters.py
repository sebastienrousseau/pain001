# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

import asyncio
import inspect
from unittest.mock import patch

from pain001.async_adapter import (
    process_files_async,
    process_files_streaming_async,
    validate_all_async,
)
from pain001.core.core import process_files, process_files_streaming
from pain001.validation import ValidationConfig, ValidationService


def test_process_files_async_wraps_sync_call() -> None:
    with patch(
        "pain001.async_adapter.asyncio.to_thread",
        autospec=True,
        return_value="generated.xml",
    ) as mock_to_thread:
        result = asyncio.run(
            process_files_async(
                "pain.001.001.11", "template.xml", "schema.xsd", "data.csv"
            )
        )
    assert result == "generated.xml"
    mock_to_thread.assert_called_once()


def test_validate_all_async_wraps_service_call() -> None:
    service = ValidationService()
    config = ValidationConfig(
        xml_message_type="pain.001.001.03",
        xml_template_file_path="template.xml",
        xsd_schema_file_path="schema.xsd",
        data_file_path="data.csv",
    )
    with patch(
        "pain001.async_adapter.asyncio.to_thread",
        autospec=True,
        return_value="ok",
    ) as mock_to_thread:
        result = asyncio.run(validate_all_async(service, config))
    assert result == "ok"
    mock_to_thread.assert_called_once()


def _parameters(function: object) -> list[tuple[str, object]]:
    """Return a function's parameter names and defaults, in order."""
    signature = inspect.signature(function)  # type: ignore[arg-type]
    return [(p.name, p.default) for p in signature.parameters.values()]


def test_async_wrappers_accept_every_sync_option() -> None:
    """The async wrappers take exactly the options of their sync twins.

    They used to stop at the data path, so output_path, output_dir,
    BAH enveloping, signing and schematron were unreachable from async
    code, and process_files_async always wrote beside the template.
    """
    assert _parameters(process_files_async) == _parameters(process_files)
    assert _parameters(process_files_streaming_async) == _parameters(
        process_files_streaming
    )


def test_process_files_async_forwards_output_path() -> None:
    """An output_path given to the async wrapper reaches process_files."""
    with patch(
        "pain001.async_adapter.process_files", return_value="out.xml"
    ) as mock_process:
        result = asyncio.run(
            process_files_async(
                "pain.001.001.03",
                "template.xml",
                "schema.xsd",
                "data.csv",
                output_path="out.xml",
                envelop_bah=True,
            )
        )
    assert result == "out.xml"
    assert mock_process.call_args.kwargs["output_path"] == "out.xml"
    assert mock_process.call_args.kwargs["envelop_bah"] is True


def test_process_files_streaming_async_forwards_output_dir() -> None:
    """An output_dir given to the async wrapper reaches the sync call."""
    with patch(
        "pain001.async_adapter.process_files_streaming",
        return_value=["a.xml"],
    ) as mock_stream:
        result = asyncio.run(
            process_files_streaming_async(
                "pain.001.001.03",
                "template.xml",
                "schema.xsd",
                "data.csv",
                chunk_size=2,
                output_dir="out",
            )
        )
    assert result == ["a.xml"]
    assert mock_stream.call_args.kwargs["output_dir"] == "out"
    assert mock_stream.call_args.kwargs["chunk_size"] == 2
