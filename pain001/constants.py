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

"""Shared constants and configuration for the pain001 library."""

import os
from pathlib import Path

# The absolute root of the package - derived safely
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()

# Shared metadata
VERSION = "0.0.47"
SCHEMAS_DIR = BASE_DIR / "schemas"
TEMPLATES_DIR = BASE_DIR / "templates"

# Valid XML types for ISO 20022 Payment Initiation
valid_xml_types = [
    "pain.001.001.03",  # Customer Credit Transfer Initiation V03
    "pain.001.001.04",  # Customer Credit Transfer Initiation V04
    "pain.001.001.05",  # Customer Credit Transfer Initiation V05
    "pain.001.001.06",  # Customer Credit Transfer Initiation V06
    "pain.001.001.07",  # Customer Credit Transfer Initiation V07
    "pain.001.001.08",  # Customer Credit Transfer Initiation V08
    "pain.001.001.09",  # Customer Credit Transfer Initiation V09
    "pain.001.001.10",  # Customer Credit Transfer Initiation V10
    "pain.001.001.11",  # Customer Credit Transfer Initiation V11
]

# Application metadata
APP_NAME = "Pain001"
APP_DESCRIPTION = """
A powerful Python library that enables you to create
ISO 20022-compliant payment files directly from CSV or SQLite Data files.\n
https://pain001.com
"""

__all__ = [
    "APP_DESCRIPTION",
    "APP_NAME",
    "BASE_DIR",
    "SCHEMAS_DIR",
    "TEMPLATES_DIR",
    "VERSION",
    "valid_xml_types",
]
