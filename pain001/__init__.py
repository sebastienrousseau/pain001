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

"""The Python pain001 module."""

import logging

__version__ = "0.0.59"

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
from pain001.camt053 import (
    build_camt053_statement,
    parse_camt053_statement,
)
from pain001.config import ConfigManager
from pain001.core.core import process_files
from pain001.exceptions import DataSourceError, PaymentValidationError
from pain001.observability import (
    MetricEvent,
    clear_metrics_callbacks,
    register_metrics_callback,
)
from pain001.pain002 import build_pain002_report, parse_pain002_report
from pain001.templates import (
    DEFAULT_TEMPLATE_REGISTRY,
    TemplateRegistry,
    validate_registry,
)
from pain001.validation import (
    SchemeValidationResult,
    SchemeViolation,
    sanitize_to_charset,
    validate_scheme,
)
from pain001.xml.generate_xml import (
    canonicalize_payment_record,
    generate_xml_string,
    normalize_payment_records,
)

__all__ = [
    "main",
    "process_files",
    "process_files_async",
    "process_files_streaming_async",
    "canonicalize_payment_record",
    "generate_xml_string",
    "generate_xml_string_async",
    "normalize_payment_records",
    "parse_pain002_report",
    "build_pain002_report",
    "parse_camt053_statement",
    "build_camt053_statement",
    "ConfigManager",
    "TemplateRegistry",
    "DEFAULT_TEMPLATE_REGISTRY",
    "validate_registry",
    "MetricEvent",
    "register_metrics_callback",
    "clear_metrics_callbacks",
    "validate_all_async",
    "validate_scheme",
    "SchemeValidationResult",
    "SchemeViolation",
    "sanitize_to_charset",
    "PaymentValidationError",
    "DataSourceError",
    "__version__",
]
