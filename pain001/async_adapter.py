# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Async-ready wrappers around the synchronous library entry points."""

from __future__ import annotations

import asyncio
from typing import Any

from pain001.core.core import process_files, process_files_streaming
from pain001.data.loader import load_payment_data
from pain001.validation.service import ValidationConfig, ValidationService
from pain001.xml.generate_xml import generate_xml_string


async def process_files_async(
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: str,
) -> str:
    """Run process_files() in a worker thread."""
    return await asyncio.to_thread(
        process_files,
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
    )


async def process_files_streaming_async(
    xml_message_type: str,
    xml_template_file_path: str,
    xsd_schema_file_path: str,
    data_file_path: str,
    chunk_size: int = 1000,
) -> list[str]:
    """Run process_files_streaming() in a worker thread."""
    return await asyncio.to_thread(
        process_files_streaming,
        xml_message_type,
        xml_template_file_path,
        xsd_schema_file_path,
        data_file_path,
        chunk_size,
    )


async def generate_xml_string_async(
    data: list[dict[str, object]],
    payment_initiation_message_type: str,
    xml_template_path: str,
    xsd_schema_path: str,
) -> str:
    """Run generate_xml_string() in a worker thread."""
    return await asyncio.to_thread(
        generate_xml_string,
        data,
        payment_initiation_message_type,
        xml_template_path,
        xsd_schema_path,
    )


async def load_payment_data_async(
    data_source: str | list[dict[str, Any]] | dict[str, Any],
) -> list[dict[str, Any]]:
    """Run load_payment_data() in a worker thread."""
    return await asyncio.to_thread(load_payment_data, data_source)


async def validate_all_async(
    validation_service: ValidationService, config: ValidationConfig
) -> Any:
    """Run ValidationService.validate_all() in a worker thread."""
    return await asyncio.to_thread(validation_service.validate_all, config)
