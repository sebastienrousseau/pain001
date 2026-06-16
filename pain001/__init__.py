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

"""The Python pain001 module."""

import logging

__version__ = "0.0.50"

# Library convention: emit nothing unless the host app configures
# logging (PEP 282 / logging HOWTO).
logging.getLogger(__name__).addHandler(logging.NullHandler())

from pain001.__main__ import main
from pain001.async_adapter import (
    generate_xml_string_async,
    process_files_async,
    process_files_streaming_async,
    validate_all_async,
)
from pain001.camt053 import parse_camt053_statement
from pain001.config import ConfigManager
from pain001.core.core import process_files
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.observability import (
    MetricEvent,
    clear_metrics_callbacks,
    register_metrics_callback,
)
from pain001.pain002 import parse_pain002_report
from pain001.templates import (
    DEFAULT_TEMPLATE_REGISTRY,
    TemplateRegistry,
    validate_registry,
)
from pain001.xml.generate_xml import generate_xml_string

__all__ = [
    "main",
    "process_files",
    "process_files_async",
    "process_files_streaming_async",
    "generate_xml_string",
    "generate_xml_string_async",
    "parse_pain002_report",
    "parse_camt053_statement",
    "ConfigManager",
    "TemplateRegistry",
    "DEFAULT_TEMPLATE_REGISTRY",
    "validate_registry",
    "MetricEvent",
    "register_metrics_callback",
    "clear_metrics_callbacks",
    "validate_all_async",
    "PaymentValidationError",
    "DataSourceError",
    "__version__",
]
