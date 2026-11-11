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

"""Prepare and render a payment message's template.

The steps every generator shares: check the inputs, normalise the rows,
build the template's data and compile the template, then render it as a
stream of chunks. Split from ``generate_xml`` so the eager and the
streamed writers use one implementation.
"""

import re
import time
from collections.abc import Iterator
from typing import Any

from jinja2 import Template

from pain001.observability import emit_metric_event
from pain001.observability.otel import set_span_attributes, traced
from pain001.security import validate_path
from pain001.xml._jinja import compile_template as _compile_template
from pain001.xml.message_registry import MESSAGE_REGISTRY, prepare_xml_data
from pain001.xml.payment_records import _normalize_financial_fields
from pain001.xml.publish import publish_stream, xsd_check

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
    normalized_data, nb_of_txs, ctrl_sum = _normalize_financial_fields(
        data, compact=True
    )

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


def prepare_render(
    data: list[dict[str, Any]],
    message_type: str,
    template_path: str,
    xsd_path: str,
) -> tuple[str, Template, dict[str, Any], int]:
    """Check the inputs and schema path, then prepare the render.

    Args:
        data: The payment rows.
        message_type: The message type (e.g. ``pain.001.001.03``).
        template_path: The Jinja2 XML template.
        xsd_path: The schema the document must pass.

    Returns:
        The validated schema path, the compiled template, its data and
        the row count.

    Raises:
        ValueError: If the message type is unknown, the data empty, or
            the template or schema path fails validation.
    """
    safe_template_path = _validate_generation_inputs(
        data, message_type, template_path
    )
    try:
        safe_xsd_path = str(validate_path(xsd_path, must_exist=True))
    except Exception as e:
        raise ValueError(f"Invalid schema path: {e}") from e
    template, xml_data, row_count = _prepare_template_and_data(
        data, message_type, safe_template_path
    )
    return safe_xsd_path, template, xml_data, row_count


def _stamp_span(message_type: str, row_count: int) -> None:
    """Name the message type and row count on the current span."""
    set_span_attributes(
        **{
            "pain001.message_type": message_type,
            "pain001.row_count": row_count,
        }
    )


def render_text(
    prepared: tuple[str, Template, dict[str, Any], int], message_type: str
) -> str:
    """Render the whole document as text; emit ``xml_rendered``.

    Args:
        prepared: What :func:`prepare_render` returned.
        message_type: The message type.

    Returns:
        The rendered document, not yet XSD-checked.
    """
    _xsd_path, template, xml_data, row_count = prepared
    _stamp_span(message_type, row_count)
    started = time.time()
    xml_content = str(template.render(**xml_data))
    emit_metric_event(
        "xml_rendered",
        message_type=message_type,
        duration_ms=int((time.time() - started) * 1000),
    )
    return xml_content


def render_chunks(
    template: Template,
    xml_data: dict[str, Any],
    message_type: str,
    buffer_size: int = 10,
) -> Iterator[str]:
    """Render ``template`` as chunks; emit ``xml_rendered`` at the end.

    The chunks join to exactly what ``template.render`` returns.
    """
    started = time.time()
    stream = template.stream(**xml_data)
    stream.enable_buffering(buffer_size)
    yield from stream
    emit_metric_event(
        "xml_rendered",
        message_type=message_type,
        duration_ms=int((time.time() - started) * 1000),
    )


@traced("pain001.render")
def render_to_file(
    prepared: tuple[str, Template, dict[str, Any], int],
    message_type: str,
    destination: str,
) -> tuple[str, int]:
    """Render straight to a staged file, XSD-check it, publish it.

    No copy of the document is held: the chunks go to the staged file
    and the schema check streams it back (bounded memory), so peak
    memory is the rows, not the document.

    Args:
        prepared: What :func:`prepare_render` returned.
        message_type: The message type.
        destination: Where the file is published.

    Returns:
        The published path and its size in bytes.

    RuntimeError from the XSD check propagates; nothing is published.
    """
    xsd_path, template, xml_data, row_count = prepared
    _stamp_span(message_type, row_count)
    return publish_stream(
        render_chunks(template, xml_data, message_type),
        destination,
        xsd_check(xsd_path, message_type),
    )


__all__ = [
    "_compile_template",
    "_load_trusted_template_source",
    "_prepare_template_and_data",
    "_validate_generation_inputs",
    "prepare_render",
    "render_chunks",
    "render_text",
    "render_to_file",
]
