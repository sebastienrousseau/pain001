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

import importlib
import logging
from typing import TYPE_CHECKING

__version__ = "0.0.83"

# Library convention: emit nothing unless the host app configures
# logging (PEP 282 / logging HOWTO).
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Every public name is imported on first use (PEP 562), so `import
# pain001` and the CLI's start-up load only what they use: the eager
# imports cost about 260 ms, most of it xmlschema, pyarrow (through the
# data loaders) and the faces chain. Type checkers read the imports
# below; the mapping is what runs.
if TYPE_CHECKING:
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
    from pain001.check import CheckReport, check_document
    from pain001.config import ConfigManager
    from pain001.core.core import process_files
    from pain001.exceptions import DataSourceError, PaymentValidationError
    from pain001.observability import (
        MetricEvent,
        clear_metrics_callbacks,
        register_metrics_callback,
    )
    from pain001.pain002 import build_pain002_report, parse_pain002_report
    from pain001.security.dsig import (
        SignatureReport,
        XmlSignatureError,
        sign_xml_document,
        verify_signature,
        verify_xml_signature,
    )
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
    from pain001.xml.envelope import (
        BusinessApplicationHeader,
        envelop_iso20022_message,
        unpack_iso20022_message,
    )
    from pain001.xml.generate_xml import (
        generate_xml_string,
        stream_xml_chunks,
        stream_xml_to_file,
    )
    from pain001.xml.payment_records import (
        canonicalize_payment_record,
        normalize_payment_records,
    )

_LAZY: dict[str, str] = {
    "generate_xml_string_async": "pain001.async_adapter",
    "process_files_async": "pain001.async_adapter",
    "process_files_streaming_async": "pain001.async_adapter",
    "validate_all_async": "pain001.async_adapter",
    "build_camt053_statement": "pain001.camt053",
    "parse_camt053_statement": "pain001.camt053",
    "CheckReport": "pain001.check",
    "check_document": "pain001.check",
    "ConfigManager": "pain001.config",
    "process_files": "pain001.core.core",
    "DataSourceError": "pain001.exceptions",
    "PaymentValidationError": "pain001.exceptions",
    "MetricEvent": "pain001.observability",
    "clear_metrics_callbacks": "pain001.observability",
    "register_metrics_callback": "pain001.observability",
    "build_pain002_report": "pain001.pain002",
    "parse_pain002_report": "pain001.pain002",
    "XmlSignatureError": "pain001.security.dsig",
    "sign_xml_document": "pain001.security.dsig",
    "verify_xml_signature": "pain001.security.dsig",
    "verify_signature": "pain001.security.dsig",
    "SignatureReport": "pain001.security.dsig",
    "DEFAULT_TEMPLATE_REGISTRY": "pain001.templates",
    "TemplateRegistry": "pain001.templates",
    "validate_registry": "pain001.templates",
    "SchemeValidationResult": "pain001.validation",
    "SchemeViolation": "pain001.validation",
    "sanitize_to_charset": "pain001.validation",
    "validate_scheme": "pain001.validation",
    "BusinessApplicationHeader": "pain001.xml.envelope",
    "envelop_iso20022_message": "pain001.xml.envelope",
    "unpack_iso20022_message": "pain001.xml.envelope",
    "generate_xml_string": "pain001.xml.generate_xml",
    "stream_xml_chunks": "pain001.xml.generate_xml",
    "stream_xml_to_file": "pain001.xml.generate_xml",
    "canonicalize_payment_record": "pain001.xml.payment_records",
    "normalize_payment_records": "pain001.xml.payment_records",
}

__all__ = [
    "main",
    "process_files",
    "process_files_async",
    "process_files_streaming_async",
    "canonicalize_payment_record",
    "generate_xml_string",
    "generate_xml_string_async",
    "normalize_payment_records",
    "stream_xml_chunks",
    "stream_xml_to_file",
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
    "check_document",
    "CheckReport",
    "validate_scheme",
    "SchemeValidationResult",
    "SchemeViolation",
    "sanitize_to_charset",
    "PaymentValidationError",
    "DataSourceError",
    "BusinessApplicationHeader",
    "envelop_iso20022_message",
    "unpack_iso20022_message",
    "sign_xml_document",
    "verify_xml_signature",
    "verify_signature",
    "SignatureReport",
    "XmlSignatureError",
    "__version__",
]


def __getattr__(name: str) -> object:
    """Import a public name on first use, and ``pain001.main`` lazily.

    The command-line entry point pulls in ``rich`` and ``click``; a program
    (or a browser runtime) that only generates and validates files should
    not pay for them, nor for the modules of names it never uses.

    Args:
        name: The attribute being looked up.

    Returns:
        The CLI entry point for ``main``, or the public name's object,
        which is then cached on the package.

    Raises:
        AttributeError: For any other name.
    """
    if name == "main":
        from pain001.__main__ import main  # noqa: PLC0415

        return main
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module 'pain001' has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the package's names, the lazy public ones included."""
    return sorted(set(globals()) | set(__all__))
