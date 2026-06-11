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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Guardrails that detect template/schema drift."""

from __future__ import annotations

import re
from pathlib import Path

from pain001.templates.registry import (
    DEFAULT_TEMPLATE_REGISTRY,
    TemplateMetadata,
    TemplateRegistry,
)


class SchemaGuardrailError(ValueError):
    """Raised when template metadata or namespaces drift."""


_MESSAGE_TYPE_PATTERN = re.compile(r"pain\.\d{3}\.\d{3}\.\d{2}")


def _extract_message_type(path: Path) -> str:
    match = _MESSAGE_TYPE_PATTERN.search(path.read_text(encoding="utf-8"))
    if not match:
        raise SchemaGuardrailError(
            f"Could not determine message type from {path}"
        )
    return match.group(0)


def validate_template_bundle(metadata: TemplateMetadata) -> None:
    """Validate one template bundle for existence and drift."""
    for required_path in [metadata.template_path, metadata.xsd_path]:
        if not required_path.exists():
            raise SchemaGuardrailError(
                f"Missing required file: {required_path}"
            )

    for candidate in [
        metadata.template_path,
        metadata.xsd_path,
        metadata.example_xml_path,
    ]:
        if candidate is None:
            continue
        discovered_message_type = _extract_message_type(candidate)
        if discovered_message_type != metadata.message_type:
            raise SchemaGuardrailError(
                f"Message type drift for {candidate}: "
                f"expected {metadata.message_type}, "
                f"found {discovered_message_type}"
            )


def validate_registry(
    registry: TemplateRegistry = DEFAULT_TEMPLATE_REGISTRY,
) -> list[str]:
    """Validate every registered template and return validated IDs."""
    validated: list[str] = []
    for metadata in registry.list_templates():
        validate_template_bundle(metadata)
        validated.append(metadata.message_type)
    return validated
