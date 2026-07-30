# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

import asyncio
from unittest.mock import patch

from pain001.async_adapter import process_files_async, validate_all_async
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
