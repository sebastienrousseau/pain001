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

# pylint: disable=duplicate-code

"""Generate and XSD-validate ISO 20022 XML payment messages."""

import logging
import os
import re
import time
import warnings
from decimal import Decimal, InvalidOperation
from typing import Any

from jinja2 import select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from pain001.exceptions import PaymentValidationError
from pain001.observability import emit_metric_event
from pain001.security import validate_path
from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)
from pain001.xml.message_registry import MESSAGE_REGISTRY, prepare_xml_data
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

logger = logging.getLogger(__name__)

# Templates are trusted, but these directives would let one pull in
# arbitrary files from disk, so they are rejected before rendering.
_TEMPLATE_DIRECTIVE_PATTERN = re.compile(
    r"{%\s*(include|import|from|extends)\b", re.IGNORECASE
)

# ISO 20022 amounts carry at most two decimal places.
_AMOUNT_EXPONENT = Decimal("0.01")


def _format_amount(value: Any, row_index: int) -> str:
    """Normalize a monetary amount to an exact two-decimal string.

    Amounts are handled with Decimal end-to-end: floats are converted via
    their shortest string representation so binary artifacts are surfaced
    (and rejected) rather than silently rounded into the payment file.

    Args:
        value: The raw amount from the input row.
        row_index: 1-based row number, used in error messages.

    Returns:
        The amount as an exact two-decimal string (e.g. "10.00").

    Raises:
        PaymentValidationError: If the amount is missing, not a number,
            not positive, or carries more than two decimal places.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount is required",
            field="payment_amount",
        )
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as e:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount {value!r} is not a number",
            field="payment_amount",
        ) from e
    if not amount.is_finite() or amount <= 0:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount must be a positive amount, "
            f"got {value!r}",
            field="payment_amount",
        )
    quantized = amount.quantize(_AMOUNT_EXPONENT)
    if amount != quantized:
        raise PaymentValidationError(
            f"Row {row_index}: payment_amount {value!r} has more than two "
            "decimal places; round it explicitly before generating",
            field="payment_amount",
        )
    return f"{quantized:.2f}"


def _normalize_financial_fields(
    data: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, str]:
    """Normalize amounts and booleans, computing batch totals from rows.

    Args:
        data: Payment rows, each carrying a "payment_amount" value.

    Returns:
        Tuple of (normalized rows, nb_of_txs, ctrl_sum) where amounts are
        two-decimal strings, booleans are XSD-style "true"/"false", and
        nb_of_txs/ctrl_sum are computed from the data instead of trusting
        caller-provided header fields.
    """
    normalized: list[dict[str, Any]] = []
    total = Decimal("0.00")
    for index, row in enumerate(data, start=1):
        formatted = _format_amount(row.get("payment_amount"), index)
        total += Decimal(formatted)
        # XSD xs:boolean only accepts "true"/"false"; Python bools from
        # typed sources (JSON, SQLite) would otherwise render as "True".
        updated = {
            key: (
                ("true" if value else "false")
                if isinstance(value, bool)
                else value
            )
            for key, value in row.items()
        }
        updated["payment_amount"] = formatted
        normalized.append(updated)
    return normalized, str(len(normalized)), f"{total:.2f}"


def _load_trusted_template_source(xml_template_path: str) -> str:
    """Read a trusted template and reject filesystem-expanding directives."""
    if not str(xml_template_path).endswith(".xml"):
        raise ValueError("Template path must point to an .xml file")

    with open(xml_template_path, encoding="utf-8") as handle:  # nosec B108
        template_source = handle.read()

    if _TEMPLATE_DIRECTIVE_PATTERN.search(template_source):
        raise ValueError(
            "Template contains disabled Jinja filesystem directives"
        )
    return template_source


def generate_xml_string(
    data: list[dict[str, object]],
    payment_initiation_message_type: str,
    xml_template_path: str,
    xsd_schema_path: str,
) -> str:
    """Generate ISO 20022 pain.001 XML content as a string (in-memory).

    This function is ideal for serverless architectures, REST APIs, and
    microservices where XML needs to be returned without writing to disk.

    Args:
        data: List of dictionaries containing payment data.
        payment_initiation_message_type: Message type (e.g., "pain.001.001.03").
        xml_template_path: Path to the Jinja2 XML template file.
        xsd_schema_path: Path to XSD schema file for validation.

    Returns:
        str: The generated and validated XML content.

    Raises:
        ValueError: If message type is invalid, data is empty, the
            template or schema path fails validation, or the template
            contains disabled Jinja filesystem directives.
        RuntimeError: If XML validation fails against XSD schema.

    PaymentValidationError from amount normalization (missing,
    non-numeric, non-positive, or over-precise payment_amount values)
    propagates unchanged.

    Examples:
        >>> data = [{"id": "MSG001", "date": "2026-01-15", ...}]
        >>> xml_str = generate_xml_string(
        ...     data,
        ...     "pain.001.001.03",
        ...     "templates/pain.001.001.03/template.xml",
        ...     "templates/pain.001.001.03/pain.001.001.03.xsd"
        ... )  # doctest: +SKIP
        >>> xml_str.startswith('<?xml')
        True
    """
    # Validate message type first so caller errors stay stable.
    if payment_initiation_message_type not in MESSAGE_REGISTRY:
        raise ValueError(
            f"Invalid XML message type: {payment_initiation_message_type}"
        )

    # Check if data is not empty before touching the filesystem.
    if not data:
        raise ValueError("No data to process - data list is empty")

    # Validate template path
    try:
        xml_template_path = validate_path(xml_template_path, must_exist=True)
    except Exception as e:
        raise ValueError(f"Invalid template path: {e}") from e

    # Validate schema path
    try:
        xsd_schema_path = validate_path(xsd_schema_path, must_exist=True)
    except Exception as e:
        raise ValueError(f"Invalid schema path: {e}") from e

    # Normalize amounts (Decimal, 2dp) and compute batch totals from the
    # rows themselves — header fields like NbOfTxs/CtrlSum must never be
    # trusted from input or the message becomes internally inconsistent.
    data, nb_of_txs, ctrl_sum = _normalize_financial_fields(data)

    # Prepare XML data using the registry-driven pipeline
    prepare_started = time.time()
    xml_data = prepare_xml_data(data, payment_initiation_message_type)
    xml_data["nb_of_txs"] = nb_of_txs
    if "payment_nb_of_txs" in xml_data:
        xml_data["payment_nb_of_txs"] = nb_of_txs
    if "ctrl_sum" in xml_data:
        xml_data["ctrl_sum"] = ctrl_sum
    emit_metric_event(
        "xml_prepared",
        message_type=payment_initiation_message_type,
        record_count=len(data),
        duration_ms=int((time.time() - prepare_started) * 1000),
    )

    template_source = _load_trusted_template_source(str(xml_template_path))
    env = SandboxedEnvironment(
        autoescape=select_autoescape(
            enabled_extensions=("xml",),
            default_for_string=True,
        ),
    )
    template = env.from_string(template_source)

    # Render the template to string
    render_started = time.time()
    xml_content = template.render(**xml_data)
    emit_metric_event(
        "xml_rendered",
        message_type=payment_initiation_message_type,
        duration_ms=int((time.time() - render_started) * 1000),
    )

    # Validate the XML content against the XSD schema
    validation_started = time.time()
    is_valid = validate_xml_string_via_xsd(xml_content, xsd_schema_path)

    if not is_valid:
        emit_metric_event(
            "validation_failed",
            message_type=payment_initiation_message_type,
            schema_path=str(xsd_schema_path),
        )
        raise RuntimeError(
            f"Generated XML failed validation against {xsd_schema_path}"
        )

    emit_metric_event(
        "xsd_validation_passed",
        message_type=payment_initiation_message_type,
        schema_path=str(xsd_schema_path),
        duration_ms=int((time.time() - validation_started) * 1000),
    )

    return xml_content


def generate_xml(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_file_path: str,
    xsd_file_path: str,
    output_path: str | None = None,
) -> str:
    """Generates an ISO 20022 pain.001 XML file from input data.

    This function writes XML to a file. For in-memory XML generation
    (serverless/API use cases), use generate_xml_string() instead.

    Args:
        data: List of dictionaries containing payment data
        payment_initiation_message_type: Message type identifier. Any
            supported version from "pain.001.001.03" through
            "pain.001.001.12", or "pain.008.001.02" for direct debits.
        xml_file_path: Path to the Jinja2 XML template file
        xsd_file_path: Path to XML schema file for validation
        output_path: Explicit path to write the generated XML file to.
            Parent directories are created if needed. When omitted, the
            file is written next to the template (deprecated behavior
            that only works when the template lives under the current
            working directory).

    Returns:
        The path the XML file was written to.

    Raises:
        ValueError: If message type is invalid, data is empty, or the
            output path fails validation. RuntimeError from XSD
            validation in generate_xml_string propagates unchanged.
    """
    # Generate XML content as string
    xml_content = generate_xml_string(
        data, payment_initiation_message_type, xml_file_path, xsd_file_path
    )

    if output_path is not None:
        safe_xml_path = os.path.realpath(str(output_path))
        os.makedirs(os.path.dirname(safe_xml_path) or ".", exist_ok=True)
    else:
        warnings.warn(
            "Calling generate_xml without output_path writes next to the "
            "template and requires it to be under the current working "
            "directory; pass output_path explicitly instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Legacy behavior: derive the output path from the template path.
        updated_xml_file_path = generate_updated_xml_file_path(
            xml_file_path, payment_initiation_message_type
        )

        try:
            safe_xml_path = validate_path(updated_xml_file_path)  # nosec B108
        except Exception as e:
            raise ValueError(f"Path validation failed: {e}") from e

        # Explicit startswith guard for CodeQL CWE-22 sanitiser recognition.
        cwd_prefix = str(os.path.realpath(os.getcwd()))
        if not safe_xml_path.startswith(cwd_prefix + os.sep):
            raise ValueError(
                f"Output path outside working directory: {safe_xml_path}"
            )

    with open(safe_xml_path, "w", encoding="utf-8") as xml_file:  # nosec B108
        xml_file.write(xml_content)

    emit_metric_event(
        "xml_generated",
        message_type=payment_initiation_message_type,
        output_path=str(safe_xml_path),
        file_size_bytes=len(xml_content.encode("utf-8")),
    )

    logger.info("XML file created at %s", safe_xml_path)
    return safe_xml_path
