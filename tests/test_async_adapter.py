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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the asyncio adapter wrappers."""

import asyncio

from pain001.async_adapter import (
    generate_xml_string_async,
    load_payment_data_async,
    validate_all_async,
)
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.validation.service import ValidationConfig, ValidationService

_TPL = TEMPLATES_DIR / "pain.001.001.03"


def test_load_payment_data_async() -> None:
    """The async loader returns the same rows as the sync loader."""
    rows = asyncio.run(load_payment_data_async(str(_TPL / "template.csv")))
    assert isinstance(rows, list)
    assert rows


def test_generate_xml_string_async() -> None:
    """The async string generator returns validated XML."""
    data = load_csv_data(str(_TPL / "template.csv"))
    xml = asyncio.run(
        generate_xml_string_async(
            data,
            "pain.001.001.03",
            str(_TPL / "template.xml"),
            str(_TPL / "pain.001.001.03.xsd"),
        )
    )
    assert xml.startswith("<?xml")


def test_validate_all_async() -> None:
    """The async validation wrapper returns a report."""
    config = ValidationConfig(
        xml_message_type="pain.001.001.03",
        xml_template_file_path=str(_TPL / "template.xml"),
        xsd_schema_file_path=str(_TPL / "pain.001.001.03.xsd"),
        data_file_path=str(_TPL / "template.csv"),
    )
    report = asyncio.run(validate_all_async(ValidationService(), config))
    assert report is not None
