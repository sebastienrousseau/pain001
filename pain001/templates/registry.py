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

"""Automatic discovery and metadata registry for bundled templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml  # type: ignore[import-untyped]

from pain001.constants import TEMPLATES_DIR


@dataclass(frozen=True)
class TemplateMetadata:
    """Describes a discovered ISO 20022 template bundle."""

    message_type: str
    message_category: str
    template_path: Path
    xsd_path: Path
    example_data_path: Optional[Path]
    example_xml_path: Optional[Path]
    supported_input_formats: list[str]
    iso_version: str
    deprecated: bool = False


class TemplateRegistry:
    """Discover and query supported template bundles."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self.templates_dir = Path(templates_dir).resolve()
        self._registry: dict[str, TemplateMetadata] = {}
        self._discover_templates()

    def _discover_templates(self) -> None:
        for metadata_path in sorted(
            self.templates_dir.glob("*/metadata.yaml")
        ):
            metadata = self._load_metadata(metadata_path)
            self._registry[metadata.message_type] = metadata

    def _load_metadata(self, metadata_path: Path) -> TemplateMetadata:
        raw_data = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
        raw = dict(raw_data)
        parent = metadata_path.parent
        files = raw.get("files", {})
        example_data = files.get("example_data")
        example_xml = files.get("example_xml")

        return TemplateMetadata(
            message_type=str(raw["message_type"]),
            message_category=str(raw["message_category"]),
            template_path=(parent / str(files["template"])).resolve(),
            xsd_path=(parent / str(files["schema"])).resolve(),
            example_data_path=(
                (parent / str(example_data)).resolve()
                if example_data
                else None
            ),
            example_xml_path=(
                (parent / str(example_xml)).resolve() if example_xml else None
            ),
            supported_input_formats=[
                str(item) for item in raw.get("supported_input_formats", [])
            ],
            iso_version=str(raw["iso_version"]),
            deprecated=bool(raw.get("deprecated", False)),
        )

    def get_template(self, message_type: str) -> TemplateMetadata:
        """Return metadata for a supported message type."""
        try:
            return self._registry[message_type]
        except KeyError as exc:
            raise KeyError(
                f"Unsupported template '{message_type}'. "
                f"Known values: {', '.join(self.list_supported_versions())}"
            ) from exc

    def list_templates(self) -> list[TemplateMetadata]:
        """Return every discovered template."""
        return [self._registry[key] for key in self.list_supported_versions()]

    def list_supported_versions(self) -> list[str]:
        """Return supported message types in sorted order."""
        return sorted(self._registry)

    def search_by_category(self, category: str) -> list[TemplateMetadata]:
        """Return templates whose category matches case-insensitively."""
        category_lower = category.lower()
        return [
            metadata
            for metadata in self.list_templates()
            if metadata.message_category.lower() == category_lower
        ]

    def resolve_paths(self, message_type: str) -> tuple[str, str]:
        """Return bundled template and schema paths for a message type."""
        metadata = self.get_template(message_type)
        return str(metadata.template_path), str(metadata.xsd_path)


DEFAULT_TEMPLATE_REGISTRY = TemplateRegistry()
