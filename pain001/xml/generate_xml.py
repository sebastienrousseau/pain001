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

# pylint: disable=duplicate-code

"""Generate and XSD-validate ISO 20022 XML payment messages."""

import logging
import re
import time
from collections.abc import Iterator
from typing import Any

from jinja2 import Template

from pain001.exceptions import PaymentValidationError
from pain001.observability import emit_metric_event
from pain001.observability.otel import set_span_attributes, traced
from pain001.security import validate_path
from pain001.xml._jinja import compile_template as _compile_template
from pain001.xml.message_registry import MESSAGE_REGISTRY, prepare_xml_data
from pain001.xml.payment_records import (
    _normalize_financial_fields,
    canonicalize_payment_record,
)
from pain001.xml.payment_records import (
    normalize_payment_records as _normalize_payment_records,
)
from pain001.xml.publish import (
    finalise_message,
    publish_stream,
    require_schematron,
    require_xsd_valid,
    resolve_output_path,
    xsd_check,
)

logger = logging.getLogger(__name__)

# Public here before the record helpers moved to payment_records
# (0.0.81); kept so existing imports from this module still work.
normalize_payment_records = _normalize_payment_records

# Templates are trusted, but these directives would let one pull in
# arbitrary files from disk, so they are rejected before rendering.
_TEMPLATE_DIRECTIVE_PATTERN = re.compile(
    r"{%\s*(include|import|from|extends)\b", re.IGNORECASE
)


def _load_trusted_template_source(xml_template_path: str) -> str:
    """Read a trusted template and reject filesystem-expanding directives."""
    if not str(xml_template_path).endswith(".xml"):
        raise ValueError("Template path must point to an .xml file")

    with open(xml_template_path, encoding="utf-8") as handle:
        template_source = handle.read()

    if _TEMPLATE_DIRECTIVE_PATTERN.search(template_source):
        raise ValueError(
            "Template contains disabled Jinja filesystem directives"
        )
    return template_source


def _validate_generation_inputs(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_template_path: str,
) -> str:
    """Validate message type, data presence, and template path.

    Args:
        data: List of dictionaries containing payment data.
        payment_initiation_message_type: Message type (e.g., "pain.001.001.03").
        xml_template_path: Path to the Jinja2 XML template file.

    Returns:
        The validated template path.

    Raises:
        ValueError: If message type is invalid, data is empty, or the
            template path fails validation.
    """
    if payment_initiation_message_type not in MESSAGE_REGISTRY:
        raise ValueError(
            f"Invalid XML message type: {payment_initiation_message_type}"
        )

    if not data:
        raise ValueError("No data to process - data list is empty")

    try:
        return str(validate_path(xml_template_path, must_exist=True))
    except Exception as e:
        raise ValueError(f"Invalid template path: {e}") from e


def _prepare_template_and_data(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    safe_template_path: str,
) -> tuple[Template, dict[str, Any], int]:
    """Prepare normalized XML template and data dictionary.

    Args:
        data: List of dictionaries containing payment data.
        payment_initiation_message_type: Message type (e.g., "pain.001.001.03").
        safe_template_path: Pre-validated path to XML template file.

    Returns:
        A tuple of (compiled Jinja2 template, prepared XML data dict, row count).
    """
    # Normalize amounts (Decimal, 2dp) and compute batch totals from the
    # rows themselves — header fields like NbOfTxs/CtrlSum must never be
    # trusted from input or the message becomes internally inconsistent.
    normalized_data, nb_of_txs, ctrl_sum = _normalize_financial_fields(data)

    # Prepare XML data using the registry-driven pipeline
    prepare_started = time.time()
    xml_data = prepare_xml_data(
        normalized_data, payment_initiation_message_type
    )
    xml_data["nb_of_txs"] = nb_of_txs
    if "payment_nb_of_txs" in xml_data:
        xml_data["payment_nb_of_txs"] = nb_of_txs
    if "ctrl_sum" in xml_data:
        xml_data["ctrl_sum"] = ctrl_sum
    emit_metric_event(
        "xml_prepared",
        message_type=payment_initiation_message_type,
        record_count=len(normalized_data),
        duration_ms=int((time.time() - prepare_started) * 1000),
    )

    template_source = _load_trusted_template_source(safe_template_path)
    template = _compile_template(template_source)
    return template, xml_data, len(normalized_data)


@traced("pain001.stream")
def stream_xml_chunks(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_template_path: str,
    buffer_size: int = 10,
) -> Iterator[str]:
    """Stream ISO 20022 pain.001 XML content as string chunks (generator).

    Provides an iterator of string chunks with constant memory overhead,
    enabling O(1) memory serialization of large payment batches directly
    to disk or network sockets without materializing the full XML document
    in memory.

    Args:
        data: List of dictionaries containing payment data.
        payment_initiation_message_type: Message type (e.g., "pain.001.001.03").
        xml_template_path: Path to the Jinja2 XML template file.
        buffer_size: Buffer size for Jinja template streaming (default 10).

    Yields:
        str: Successive string chunks of the rendered XML document.

    A ``ValueError`` from invalid message type, empty data, or invalid
    template path propagates unchanged.
    """
    safe_template_path = _validate_generation_inputs(
        data, payment_initiation_message_type, xml_template_path
    )
    template, xml_data, row_count = _prepare_template_and_data(
        data, payment_initiation_message_type, safe_template_path
    )

    set_span_attributes(
        **{
            "pain001.message_type": payment_initiation_message_type,
            "pain001.row_count": row_count,
            "pain001.streaming": True,
        }
    )
    render_started = time.time()
    stream = template.stream(**xml_data)
    if buffer_size >= 5:
        stream.enable_buffering(buffer_size)
    yield from stream
    emit_metric_event(
        "xml_stream_rendered",
        message_type=payment_initiation_message_type,
        duration_ms=int((time.time() - render_started) * 1000),
    )


@traced("pain001.write.stream")
def _prepare_stream_target(
    data: list[dict[str, Any]],
    message_type: str,
    template_path: str,
    output_path: str,
    xsd_schema_path: str | None,
) -> tuple[str, str]:
    """Check a streamed write's inputs, paths, schema and rows up front.

    Args:
        data: The payment rows.
        message_type: The target message type.
        template_path: The Jinja2 template the rows will be rendered by.
        output_path: Where the caller wants the file.
        xsd_schema_path: The schema, or ``None`` for the bundled one.

    Returns:
        The validated output path and schema path.

    Raises:
        ValueError: If the message type is unknown, the data empty, or
            the template, output or schema path fails validation.
        PaymentValidationError: If the rows break the message type's
            column contract.
    """
    from pain001.csv.validate_csv_data import validate_csv_data

    _validate_generation_inputs(data, message_type, template_path)
    try:
        safe_output = validate_path(output_path)
    except Exception as e:
        raise ValueError(f"Invalid output path: {e}") from e
    if xsd_schema_path is None:
        from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

        template = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type)
        xsd_schema_path = str(template.xsd_path)
    try:
        safe_xsd = validate_path(xsd_schema_path, must_exist=True)
    except Exception as e:
        raise ValueError(f"Invalid schema path: {e}") from e
    rows = [canonicalize_payment_record(row) for row in data]
    if not validate_csv_data(rows, message_type):
        raise PaymentValidationError(
            f"Row validation failed for {message_type}; the log names "
            "each missing or mistyped column",
            field="records",
        )
    return safe_output, safe_xsd


def stream_xml_to_file(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_template_path: str,
    output_path: str,
    buffer_size: int = 10,
    xsd_schema_path: str | None = None,
) -> str:
    """Stream ISO 20022 pain.001 XML directly to a file with constant memory.

    Rows are checked against the message type's column contract; the
    document is staged next to ``output_path``, XSD-validated there and
    renamed into place only when valid.

    Args:
        data: List of dictionaries containing payment data.
        payment_initiation_message_type: Message type identifier.
        xml_template_path: Path to the Jinja2 XML template file.
        output_path: Destination filesystem path for the XML file.
        buffer_size: Buffer size for streaming chunks (default 10).
        xsd_schema_path: The schema to validate against; the bundled
            one for the message type when omitted.

    Returns:
        The canonical path the XML file was written to.

    ``ValueError`` (inputs, paths), ``PaymentValidationError`` (rows)
    and ``RuntimeError`` (XSD) propagate; none leaves a file behind.
    """
    safe_xml_path, safe_xsd_path = _prepare_stream_target(
        data,
        payment_initiation_message_type,
        xml_template_path,
        output_path,
        xsd_schema_path,
    )
    chunks = stream_xml_chunks(
        data,
        payment_initiation_message_type,
        xml_template_path,
        buffer_size=buffer_size,
    )
    safe_xml_path, total_bytes = publish_stream(
        chunks,
        safe_xml_path,
        xsd_check(safe_xsd_path, payment_initiation_message_type),
    )

    emit_metric_event(
        "xml_generated",
        message_type=payment_initiation_message_type,
        output_path=str(safe_xml_path),
        file_size_bytes=total_bytes,
        streaming=True,
    )
    logger.info(
        "XML file streamed to %s (%d bytes)", safe_xml_path, total_bytes
    )
    return safe_xml_path


@traced("pain001.render")
def generate_xml_string(
    data: list[dict[str, Any]],
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

    RuntimeError from XSD validation (every violation listed) and
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
    safe_template_path = _validate_generation_inputs(
        data,
        payment_initiation_message_type,
        xml_template_path,
    )

    # Validate schema path
    try:
        xsd_schema_path = validate_path(xsd_schema_path, must_exist=True)
    except Exception as e:
        raise ValueError(f"Invalid schema path: {e}") from e

    template, xml_data, row_count = _prepare_template_and_data(
        data,
        payment_initiation_message_type,
        safe_template_path,
    )

    set_span_attributes(
        **{
            "pain001.message_type": payment_initiation_message_type,
            "pain001.row_count": row_count,
        }
    )
    # Render the template to string
    render_started = time.time()
    xml_content = template.render(**xml_data)
    emit_metric_event(
        "xml_rendered",
        message_type=payment_initiation_message_type,
        duration_ms=int((time.time() - render_started) * 1000),
    )

    # Validate the XML content against the XSD schema; every violation
    # is reported at once (element path + reason) so a caller can fix
    # all inputs in a single retry.
    require_xsd_valid(
        xml_content, xsd_schema_path, payment_initiation_message_type
    )

    return str(xml_content)


@traced("pain001.write")
def generate_xml(
    data: list[dict[str, Any]],
    payment_initiation_message_type: str,
    xml_file_path: str,
    xsd_file_path: str,
    output_path: str | None = None,
    envelop_bah: bool = False,
    bah_header: Any | None = None,
    xml_sign_key: str | bytes | None = None,
    xml_sign_cert: str | bytes | None = None,
    xml_sign_passphrase: str | bytes | None = None,
    schematron: str | Any | None = None,
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
        envelop_bah: If True, wrap generated XML in an ISO 20022 BAH envelope.
        bah_header: Optional customized BusinessApplicationHeader instance.
        xml_sign_key: Optional RSA private key in PEM format to sign the XML.
        xml_sign_cert: Optional X.509 certificate in PEM format for KeyInfo.
        xml_sign_passphrase: Optional passphrase for the private key.
        schematron: Optional Schematron rulebook preset or .sch path the
            final document must pass before it is written.

    Returns:
        The path the XML file was written to.

    Raises:
        ValueError: If message type is invalid, data is empty, or the
            output path fails validation. RuntimeError from XSD
            validation in generate_xml_string and XMLGenerationError
            from Schematron propagate unchanged, and nothing is written.
    """
    # Generate XML content as string
    xml_content = generate_xml_string(
        data, payment_initiation_message_type, xml_file_path, xsd_file_path
    )

    xml_content = finalise_message(
        xml_content,
        envelop_bah,
        bah_header,
        xml_sign_key,
        xml_sign_cert,
        xml_sign_passphrase,
    )
    safe_xml_path = resolve_output_path(
        output_path, xml_file_path, payment_initiation_message_type
    )
    if schematron is not None:
        require_schematron(
            xml_content,
            schematron,
            f"Schematron rulebook validation failed for '{safe_xml_path}'",
        )

    from pain001.plugins.registry import registry as plugin_registry

    writer = plugin_registry.get_writer("xml-file")
    if writer is None:
        raise ValueError("The xml-file writer plugin is disabled")
    safe_xml_path = writer.write(xml_content, safe_xml_path)

    emit_metric_event(
        "xml_generated",
        message_type=payment_initiation_message_type,
        output_path=str(safe_xml_path),
        file_size_bytes=len(xml_content.encode("utf-8")),
    )

    logger.info("XML file created at %s", safe_xml_path)
    return safe_xml_path
