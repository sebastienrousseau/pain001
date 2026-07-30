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

"""Hierarchical configuration loader for CLI and library usage."""

from __future__ import annotations

import configparser
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from pain001.constants import BASE_DIR

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


DEFAULT_CONFIG: dict[str, Any] = {
    "xml_message_type": None,
    "xml_template_file_path": None,
    "xsd_schema_file_path": None,
    "data_file_path": None,
    "output_dir": None,
    "streaming": False,
    "chunk_size": 1000,
    "emit_metrics": False,
}

ENV_MAPPING = {
    "PAIN001_MESSAGE_TYPE": "xml_message_type",
    "PAIN001_TEMPLATE_PATH": "xml_template_file_path",
    "PAIN001_SCHEMA_PATH": "xsd_schema_file_path",
    "PAIN001_DATA_PATH": "data_file_path",
    "PAIN001_OUTPUT_DIR": "output_dir",
    "PAIN001_STREAMING": "streaming",
    "PAIN001_CHUNK_SIZE": "chunk_size",
    "PAIN001_EMIT_METRICS": "emit_metrics",
}

ALLOWED_TOP_LEVEL_KEYS = {
    "xml_message_type",
    "xml_template_file_path",
    "xsd_schema_file_path",
    "data_file_path",
    "output_dir",
    "streaming",
    "chunk_size",
    "emit_metrics",
    "profiles",
}


class ConfigManager:
    """Load and merge project, user, env, preset, and CLI configuration."""

    def __init__(self) -> None:
        self.schema_path = BASE_DIR / "config" / "schema.yaml"
        self.presets_path = BASE_DIR / "config" / "presets.yaml"
        self.schema = yaml.safe_load(
            self.schema_path.read_text(encoding="utf-8")
        )
        self.presets = yaml.safe_load(
            self.presets_path.read_text(encoding="utf-8")
        )

    def discover_project_config(self) -> Path | None:
        """Return the first project config found in the cwd."""
        for filename in [
            "pain001.yaml",
            "pain001.yml",
            "pain001.toml",
            "pain001.ini",
        ]:
            candidate = Path.cwd() / filename
            if candidate.exists():
                return candidate
        return None

    def discover_user_config(self) -> Path | None:
        """Return the default user config path if present."""
        config_home = Path.home() / ".config" / "pain001"
        for filename in ["config.yaml", "config.yml", "config.toml"]:
            candidate = config_home / filename
            if candidate.exists():
                return candidate
        return None

    def load_from_file(self, path: str | Path) -> dict[str, Any]:
        """Load one config file in YAML, TOML, or INI format."""
        config_path = Path(path)
        suffix = config_path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            data = loaded or {}
        elif suffix == ".toml":
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        elif suffix == ".ini":
            parser = configparser.ConfigParser()
            parser.read(config_path)
            data = {
                "xml_template_file_path": parser.get(
                    "Paths", "xml_template_file_path", fallback=None
                ),
                "xsd_schema_file_path": parser.get(
                    "Paths", "xsd_schema_file_path", fallback=None
                ),
                "data_file_path": parser.get(
                    "Paths", "data_file_path", fallback=None
                ),
            }
        else:
            raise ValueError(f"Unsupported config format: {config_path}")
        self._validate_schema(data)
        return data

    def resolve(self, cli_args: Mapping[str, Any]) -> dict[str, Any]:
        """Merge defaults, user/project config, env, profile, and CLI args."""
        merged: dict[str, Any] = dict(DEFAULT_CONFIG)

        user_config = self.discover_user_config()
        if user_config:
            merged = self._deep_merge(merged, self.load_from_file(user_config))

        project_config = self.discover_project_config()
        if project_config:
            merged = self._deep_merge(
                merged, self.load_from_file(project_config)
            )

        config_path = cli_args.get("config_file")
        if config_path:
            merged = self._deep_merge(
                merged, self.load_from_file(str(config_path))
            )

        merged = self._deep_merge(merged, self._load_from_env())

        profile_name = cli_args.get("profile")
        if profile_name:
            available_profiles: dict[str, Any] = {}
            available_profiles.update(self.presets.get("profiles", {}))
            available_profiles.update(merged.get("profiles", {}))
            try:
                merged = self._deep_merge(
                    merged, available_profiles[profile_name]
                )
            except KeyError as exc:
                raise KeyError(f"Unknown profile '{profile_name}'") from exc

        merged = self._apply_cli_overrides(merged, cli_args)
        self._validate_schema(merged)
        return merged

    def get_profile(self, profile_name: str) -> dict[str, Any]:
        """Return a built-in preset or user-defined profile."""
        preset = self.presets.get("profiles", {}).get(profile_name)
        if preset:
            return dict(preset)
        project_config = self.discover_project_config()
        if project_config:
            profiles = self.load_from_file(project_config).get("profiles", {})
            if profile_name in profiles:  # pragma: no cover
                return dict(profiles[profile_name])
        raise KeyError(f"Unknown profile '{profile_name}'")

    def _load_from_env(self) -> dict[str, Any]:
        """Build a config dict from the PAIN001_* environment variables."""
        data: dict[str, Any] = {}
        for env_name, target_name in ENV_MAPPING.items():
            value = os.getenv(env_name)
            if value is None:
                continue
            data[target_name] = self._coerce_value(target_name, value)
        return data

    def _apply_cli_overrides(
        self, merged: dict[str, Any], cli_args: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Overlay non-None CLI arguments onto the merged config."""
        for key in DEFAULT_CONFIG:
            if key in cli_args and cli_args[key] is not None:
                merged[key] = cli_args[key]
        return merged

    def _coerce_value(self, key: str, value: Any) -> Any:
        """Coerce string values to the boolean or integer type a key expects."""
        if key in {"streaming", "emit_metrics"}:
            if isinstance(value, bool):  # pragma: no cover
                return value  # pragma: no cover
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        if key == "chunk_size":
            return int(value)
        return value

    def _validate_schema(self, data: Mapping[str, Any]) -> None:
        """Reject unknown top-level keys and invalid chunk_size or profiles."""
        unknown = set(data) - ALLOWED_TOP_LEVEL_KEYS
        if unknown:
            raise ValueError(
                f"Unknown config keys: {', '.join(sorted(unknown))}"
            )
        chunk_size = data.get("chunk_size")
        if chunk_size is not None and int(chunk_size) < 1:
            raise ValueError("chunk_size must be >= 1")
        if "profiles" in data and data["profiles"] is not None:
            if not isinstance(data["profiles"], dict):
                raise ValueError("profiles must be a mapping")

    def _deep_merge(
        self, base: dict[str, Any], override: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Recursively merge override into base, skipping None values."""
        merged = dict(base)
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(
                value, dict
            ):  # pragma: no cover
                merged[key] = self._deep_merge(
                    merged[key], value
                )  # pragma: no cover
            elif value is not None:  # pragma: no cover
                merged[key] = value
        return merged
