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

# XML generator function that creates the XML file from the CSV data
# and the mapping dictionary between XML tags and CSV columns names and
# writes it to a file in the same directory as the CSV file

# pylint: disable=duplicate-code

# Import the CSV library
import os
import re
import time
from typing import Any

from jinja2 import select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from pain001.observability import emit_metric_event
from pain001.security import validate_path
from pain001.xml.generate_updated_xml_file_path import (
    generate_updated_xml_file_path,
)
from pain001.xml.message_registry import MESSAGE_REGISTRY, prepare_xml_data
from pain001.xml.validate_via_xsd import validate_xml_string_via_xsd

_TEMPLATE_DIRECTIVE_PATTERN = re.compile(
    r"{%\s*(include|import|from|extends)\b", re.IGNORECASE
)


def _load_trusted_template_source(xml_template_path: str) -> str:
    """Read a trusted template and reject filesystem-expanding directives."""
    if not str(xml_template_path).endswith(".xml"):
        raise ValueError("Template path must point to an .xml file")

    with open(xml_template_path, "r", encoding="utf-8") as handle:  # nosec B108
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
        ValueError: If message type is invalid or data is empty.
        RuntimeError: If XML validation fails against XSD schema.

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

    # Prepare XML data using appropriate function
    prepare_started = time.time()
    xml_data = prepare_xml_data(data, payment_initiation_message_type)
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
) -> str:
    """Generates an ISO 20022 pain.001 XML file from input data.

    This function writes XML to a file. For in-memory XML generation
    (serverless/API use cases), use generate_xml_string() instead.

    Args:
        data: List of dictionaries containing payment data
        payment_initiation_message_type: String indicating message type
        such as "pain.001.001.03, pain.001.001.04, pain.001.001.05,
        pain.001.001.06, pain.001.001.07, pain.001.001.08, etc."
        xml_file_path: Path to write generated XML file to
        xsd_file_path: Path to XML schema file for validation

    Returns:
        str: The generated XML file path.

    Raises:
        ValueError: If message type is invalid or data is empty.
        RuntimeError: If XML validation fails.
    """
    # Generate XML content as string
    xml_content = generate_xml_string(
        data, payment_initiation_message_type, xml_file_path, xsd_file_path
    )

    # Generate updated XML file path
    updated_xml_file_path = generate_updated_xml_file_path(
        xml_file_path, payment_initiation_message_type
    )

    # Validate path to prevent traversal attacks

    try:
        safe_xml_path = validate_path(updated_xml_file_path)  # nosec B108
    except Exception as e:
        raise ValueError(f"Path validation failed: {e}") from e

    # Explicit startswith guard for CodeQL CWE-22 sanitiser recognition.
    # validate_path already enforces this, but CodeQL requires the guard
    # at the call site for interprocedural taint tracking.
    cwd_prefix = str(os.path.realpath(os.getcwd()))
    if not safe_xml_path.startswith(cwd_prefix + os.sep):
        raise ValueError(
            f"Output path outside working directory: {safe_xml_path}"
        )

    # Write the XML content to the file (now safe after validation)
    with open(safe_xml_path, "w", encoding="utf-8") as xml_file:  # nosec B108
        xml_file.write(xml_content)

    emit_metric_event(
        "xml_generated",
        message_type=payment_initiation_message_type,
        output_path=str(safe_xml_path),
        file_size_bytes=len(xml_content.encode("utf-8")),
    )

    print(f"A new XML file has been created at `{safe_xml_path}`")
    print(f"The XML has been validated against `{xsd_file_path}`")

    return safe_xml_path
