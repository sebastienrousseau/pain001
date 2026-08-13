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

"""Pain001 MCP server (stdio transport).

Tools, resources, and prompts are thin adapters over the existing core
functions. Unlike the REST API, the MCP tools take **inline data**
(a list of payment-row dicts) and return XML as a string, because an MCP
client does not share the server's filesystem.

Run it with::

    pain001-mcp
"""

import csv
import io
from typing import Any

from mcp.server.mcpserver import MCPServer

from pain001 import generate_xml_string, validate_scheme
from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.validation.schema_validator import SchemaValidator

mcp = MCPServer("pain001")


def _require_message_type(message_type: str) -> None:
    """Reject an unsupported message type.

    Args:
        message_type: The ISO 20022 message type to check.

    Raises:
        ValueError: If the message type is not supported.
    """
    if message_type not in valid_xml_types:
        supported = ", ".join(valid_xml_types)
        raise ValueError(
            f"Unsupported message type '{message_type}'. "
            f"Supported: {supported}"
        )


def _bundled_paths(message_type: str) -> tuple[str, str]:
    """Return the bundled (template, xsd) paths for a message type.

    Args:
        message_type: The ISO 20022 message type.

    Returns:
        A tuple of ``(template_path, xsd_path)``.
    """
    base = TEMPLATES_DIR / message_type
    return str(base / "template.xml"), str(base / f"{message_type}.xsd")


@mcp.tool()
def list_supported_versions() -> list[str]:
    """List every ISO 20022 message type Pain001 can generate.

    Returns:
        The supported message type identifiers.
    """
    return list(valid_xml_types)


@mcp.tool()
def inspect_template(message_type: str) -> dict[str, Any]:
    """Return the payment-row columns a message type expects.

    Args:
        message_type: The ISO 20022 message type (e.g. ``pain.001.001.03``).

    Returns:
        A dict with the message type and its required column names.
        Raises ``ValueError`` for an unsupported message type.
    """
    _require_message_type(message_type)
    sample = TEMPLATES_DIR / message_type / "template.csv"
    reader = csv.reader(io.StringIO(sample.read_text(encoding="utf-8")))
    columns = next(reader, [])
    return {"message_type": message_type, "columns": columns}


@mcp.tool()
def generate_payment_file(
    message_type: str, rows: list[dict[str, Any]]
) -> str:
    """Generate validated ISO 20022 XML from inline payment rows.

    Args:
        message_type: The ISO 20022 message type to generate.
        rows: Payment rows as a list of dicts (one per transaction).

    Returns:
        The validated XML document as a string.

    Raises:
        ValueError: If the message type is not supported or rows are empty.
    """
    _require_message_type(message_type)
    if not rows:
        raise ValueError("rows must not be empty")
    template, xsd = _bundled_paths(message_type)
    return generate_xml_string(rows, message_type, template, xsd)


@mcp.tool()
def validate_payment_data(
    message_type: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Validate payment rows against the message type's schema (dry run).

    Args:
        message_type: The ISO 20022 message type.
        rows: Payment rows as a list of dicts.

    Returns:
        A dict with ``is_valid``, ``total_rows``, ``valid_rows``, and a
        list of ``errors`` (field, message). Raises ``ValueError`` for an
        unsupported message type.
    """
    _require_message_type(message_type)
    validator = SchemaValidator(message_type)
    total, valid, errors = validator.validate_batch(rows)
    flattened = [
        {"row": index, "field": err.path, "message": err.message}
        for index, row_errors in errors
        for err in row_errors
    ]
    return {
        "is_valid": not flattened,
        "total_rows": total,
        "valid_rows": valid,
        "errors": flattened,
    }


@mcp.tool()
def validate_payment_scheme(
    rows: list[dict[str, Any]], profile: str = "sepa-sct"
) -> dict[str, Any]:
    """Validate rows against a payment-scheme rulebook (e.g. SEPA).

    Args:
        rows: Payment rows as a list of dicts.
        profile: The scheme profile name (``sepa-sct``, ``sepa-sdd``, ``sepa-b2b``, ``sepa-inst``, or ``xborder-ct``).

    Returns:
        A dict with ``profile``, ``is_valid``, and structured
        ``violations`` (rule, message, field, remediation). Raises
        ``ValueError`` for an unknown profile.
    """
    result = validate_scheme(rows, profile)
    return {
        "profile": result.profile,
        "is_valid": result.is_valid,
        "violations": [v.as_dict() for v in result.violations],
    }


@mcp.resource("pain001://schema/{message_type}")
def schema_resource(message_type: str) -> str:
    """Return the official XSD schema text for a message type.

    Args:
        message_type: The ISO 20022 message type.

    Returns:
        The XSD schema contents. Raises ``ValueError`` for an unsupported
        message type.
    """
    _require_message_type(message_type)
    xsd = TEMPLATES_DIR / message_type / f"{message_type}.xsd"
    return xsd.read_text(encoding="utf-8")


@mcp.prompt()
def build_payment_batch(message_type: str = "pain.001.001.03") -> str:
    """Guided prompt for assembling a compliant payment batch.

    Args:
        message_type: The target ISO 20022 message type.

    Returns:
        A prompt string instructing the model how to proceed.
    """
    return (
        f"Help me build a compliant {message_type} batch. First call "
        f"inspect_template('{message_type}') for the required columns, "
        "collect one dict per payment with those fields, validate them "
        "with validate_payment_data (and validate_payment_scheme for "
        "SEPA), then call generate_payment_file to produce the XML."
    )


def main() -> None:  # pragma: no cover - process entry point
    """Run the Pain001 MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
