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
import os
import time
from collections.abc import Iterator
from typing import Any, NamedTuple

from pain001.exceptions import PaymentValidationError
from pain001.observability import emit_metric_event
from pain001.observability.otel import set_span_attributes, traced
from pain001.security import validate_path
from pain001.xml._render import (
    _prepare_template_and_data as _prepare_template_and_data,
)
from pain001.xml._render import (
    _validate_generation_inputs,
    prepare_render,
    render_text,
    render_to_file,
)
from pain001.xml.payment_records import canonical_for_reading
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
    # Read-only: the rows are checked, never changed, so a row already
    # in canonical form is checked as it is rather than copied.
    rows = [canonical_for_reading(row) for row in data]
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

    A ValueError (an invalid message type, empty data, a template or
    schema path that fails validation, or a template with disabled
    Jinja filesystem directives), a RuntimeError from XSD validation
    (every violation listed) and a PaymentValidationError from amount
    normalization (missing, non-numeric, non-positive, or over-precise
    payment_amount values) propagate unchanged.

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
    mt = payment_initiation_message_type
    prepared = prepare_render(data, mt, xml_template_path, xsd_schema_path)
    xml_content = render_text(prepared, mt)
    # Every violation is reported at once (element path + reason) so a
    # caller can fix all inputs in a single retry.
    require_xsd_valid(xml_content, prepared[0], mt)
    return xml_content


def _written_size(path: str, xml_content: str) -> int:
    """The file's size on disk; the text's if a plugin wrote elsewhere."""
    try:
        return os.path.getsize(path)
    except OSError:
        return len(xml_content.encode("utf-8"))


class _Request(NamedTuple):
    """What :func:`generate_xml` was asked to write."""

    data: list[dict[str, Any]]
    message_type: str
    template: str
    xsd: str
    output_path: str | None
    envelop_bah: bool
    bah_header: Any | None
    sign_key: str | bytes | None
    sign_cert: str | bytes | None
    sign_passphrase: str | bytes | None
    schematron: Any | None


def _renders_to_file(writer: Any, request: _Request) -> bool:
    """Whether the message can be rendered straight to the file.

    An envelope, a signature, Schematron or a plugin writer needs the
    whole document as text; the plain file case does not.
    """
    from pain001.plugins._builtins import _XmlFileWriter

    return (
        isinstance(writer, _XmlFileWriter)
        and not request.envelop_bah
        and request.bah_header is None
        and request.sign_key is None
        and request.schematron is None
    )


def _finished_text(request: _Request) -> str:
    """The XSD-valid message, enveloped and signed as asked."""
    return finalise_message(
        generate_xml_string(
            request.data, request.message_type, request.template, request.xsd
        ),
        request.envelop_bah,
        request.bah_header,
        request.sign_key,
        request.sign_cert,
        request.sign_passphrase,
    )


def _write_text(
    writer: Any, xml_content: str, path: str, schematron: Any | None
) -> tuple[str, int]:
    """Check ``xml_content`` against Schematron, hand it to ``writer``.

    Args:
        writer: The xml-file writer plugin, or ``None`` when disabled.
        xml_content: The finished document.
        path: Where it goes.
        schematron: The rulebook it must pass, if any.

    Returns:
        The written path and its size.

    Raises:
        ValueError: If the xml-file writer plugin is disabled.
    """
    if schematron is not None:
        require_schematron(
            xml_content,
            schematron,
            f"Schematron rulebook validation failed for '{path}'",
        )
    if writer is None:
        raise ValueError("The xml-file writer plugin is disabled")
    path = writer.write(xml_content, path)
    return path, _written_size(path, xml_content)


# resolve_output_path's deprecation warning names generate_xml's caller:
# past _write_message, generate_xml and its tracing wrapper.
_CALLER = 5


def _write_message(request: _Request) -> str:
    """Render, check and publish the message ``request`` describes.

    The plain file case renders straight into the staged file and
    checks it as it streams back, so no copy of the document is held;
    otherwise the text is built, finished and handed to the writer.
    Inputs are checked before the output directory is created.
    """
    from pain001.plugins.registry import registry as plugin_registry

    writer = plugin_registry.get_writer("xml-file")
    where = (request.output_path, request.template, request.message_type)
    if _renders_to_file(writer, request):
        prepared = prepare_render(
            request.data, request.message_type, request.template, request.xsd
        )
        path = resolve_output_path(*where, stacklevel=_CALLER)
        path, size = render_to_file(prepared, request.message_type, path)
    else:
        content = _finished_text(request)
        path = resolve_output_path(*where, stacklevel=_CALLER)
        path, size = _write_text(writer, content, path, request.schematron)
    emit_metric_event(
        "xml_generated",
        message_type=request.message_type,
        output_path=str(path),
        file_size_bytes=size,
    )
    logger.info("XML file created at %s", path)
    return path


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
    """Generate an ISO 20022 payment message file from rows.

    For the XML as a string (an API response), use generate_xml_string.

    Args:
        data: The payment rows.
        payment_initiation_message_type: Any supported message type
            (``pain001 versions`` lists them).
        xml_file_path: The Jinja2 XML template.
        xsd_file_path: The XSD the message must pass.
        output_path: Where to write the file; missing directories are
            created. Omitted, the file goes next to the template
            (deprecated; the template must be under the working
            directory).
        envelop_bah: Wrap the message in an ISO 20022 BAH envelope.
        bah_header: A customised BusinessApplicationHeader.
        xml_sign_key: RSA private key (PEM) to sign the XML with.
        xml_sign_cert: X.509 certificate (PEM) for KeyInfo.
        xml_sign_passphrase: Passphrase for the private key.
        schematron: A Schematron rulebook preset or .sch path the
            message must pass before it is written.

    Returns:
        The path the file was written to.

    A ValueError (an invalid message type, data or output path), a
    RuntimeError (XSD) or an XMLGenerationError (Schematron) propagates,
    and nothing is written.
    """
    return _write_message(
        _Request(
            data,
            payment_initiation_message_type,
            xml_file_path,
            xsd_file_path,
            output_path,
            envelop_bah,
            bah_header,
            xml_sign_key,
            xml_sign_cert,
            xml_sign_passphrase,
            schematron,
        )
    )
