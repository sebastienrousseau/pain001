# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""ConfigManager's file names, paths and messages, pinned exactly.

The behavioural tests in ``test_config_manager.py`` exercise loading
and merging, but a renamed config file, a changed schema path or an
altered error message passed them. These tests fix each detail. Paths
are compared as strings, so a case change fails here even on a
case-insensitive filesystem.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from pain001.config import ConfigManager
from pain001.constants import BASE_DIR


def _found(directory: Path, name: str) -> str | None:
    """The file name discovery returns when only ``name`` exists."""
    (directory / name).write_text("chunk_size: 5\n", encoding="utf-8")
    try:
        manager = ConfigManager()
        found = (
            manager.discover_user_config()
            if name.startswith("config.")
            else manager.discover_project_config()
        )
        return None if found is None else found.name
    finally:
        (directory / name).unlink()


def test_the_schema_and_presets_are_read_from_the_package() -> None:
    """Both files come from ``config/`` and are parsed as UTF-8 YAML."""
    manager = ConfigManager()
    assert str(manager.schema_path) == str(BASE_DIR / "config" / "schema.yaml")
    assert str(manager.presets_path) == str(
        BASE_DIR / "config" / "presets.yaml"
    )
    assert manager.schema == yaml.safe_load(
        (BASE_DIR / "config" / "schema.yaml").read_text(encoding="utf-8")
    )
    assert manager.presets == yaml.safe_load(
        (BASE_DIR / "config" / "presets.yaml").read_text(encoding="utf-8")
    )


def test_the_package_files_are_read_as_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The encoding is named, not left to the locale."""
    encodings: list[Any] = []
    real = Path.read_text

    def spy(self: Path, *args: Any, **kwargs: Any) -> str:
        """Record the encoding, then read as usual."""
        encodings.append(kwargs.get("encoding"))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    ConfigManager()
    assert encodings == ["utf-8", "utf-8"]


@pytest.mark.parametrize(
    "name", ["pain001.yaml", "pain001.yml", "pain001.toml", "pain001.ini"]
)
def test_each_project_config_name_is_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Each supported project file is found under its exact name."""
    monkeypatch.chdir(tmp_path)
    assert _found(tmp_path, name) == name


@pytest.mark.parametrize("name", ["config.yaml", "config.yml", "config.toml"])
def test_each_user_config_name_is_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Each supported user file is found under its exact name."""
    home = tmp_path / ".config" / "pain001"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _found(home, name) == name


def test_resolve_applies_a_builtin_preset_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A profile named on the command line can come from the presets."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    resolved = ConfigManager().resolve({"profile": "sepa_direct_debit"})
    assert resolved["xml_message_type"] == "pain.008.001.02"


def test_unknown_keys_are_listed_sorted_and_comma_separated() -> None:
    """Every unknown key is named, in order, in one message."""
    with pytest.raises(ValueError) as caught:
        ConfigManager()._validate_schema({"zeta": 1, "alpha": 2})
    assert str(caught.value) == "Unknown config keys: alpha, zeta"


def test_a_chunk_size_of_one_is_accepted() -> None:
    """One is the smallest chunk size; only below it is refused."""
    ConfigManager()._validate_schema({"chunk_size": 1})
    with pytest.raises(ValueError) as caught:
        ConfigManager()._validate_schema({"chunk_size": 0})
    assert str(caught.value) == "chunk_size must be >= 1"


def test_a_non_mapping_profiles_value_is_refused_by_name() -> None:
    """``profiles`` must be a mapping, and the message says so."""
    with pytest.raises(ValueError) as caught:
        ConfigManager()._validate_schema({"profiles": ["v12"]})
    assert re.fullmatch(r"profiles must be a mapping", str(caught.value))


def test_resolve_works_when_the_presets_define_no_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project profile still resolves if the presets have none."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "pain001.yaml").write_text(
        "profiles:\n  local:\n    chunk_size: 9\n", encoding="utf-8"
    )
    manager = ConfigManager()
    manager.presets = {}
    assert manager.resolve({"profile": "local"})["chunk_size"] == 9
