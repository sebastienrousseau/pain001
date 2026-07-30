# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

import pytest

from pain001.config import ConfigManager


def test_config_manager_loads_yaml_config(tmp_path) -> None:
    config_path = tmp_path / "pain001.yaml"
    config_path.write_text(
        "xml_message_type: pain.001.001.12\nchunk_size: 250\n",
        encoding="utf-8",
    )
    manager = ConfigManager()
    loaded = manager.load_from_file(config_path)
    assert loaded["xml_message_type"] == "pain.001.001.12"
    assert loaded["chunk_size"] == 250


def test_config_manager_profile_overrides(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "pain001.yaml"
    config_path.write_text(
        "\n".join(
            [
                "profiles:",
                "  v12:",
                "    xml_message_type: pain.001.001.12",
                "    streaming: true",
            ]
        ),
        encoding="utf-8",
    )
    manager = ConfigManager()
    resolved = manager.resolve(
        {
            "config_file": None,
            "profile": "v12",
            "xml_message_type": None,
            "xml_template_file_path": None,
            "xsd_schema_file_path": None,
            "data_file_path": "payments.csv",
            "output_dir": None,
            "streaming": False,
            "chunk_size": 1000,
            "emit_metrics": False,
        }
    )
    assert resolved["xml_message_type"] == "pain.001.001.12"


def test_config_manager_env_overrides(monkeypatch) -> None:
    manager = ConfigManager()
    monkeypatch.setenv("PAIN001_CHUNK_SIZE", "42")
    resolved = manager.resolve(
        {
            "config_file": None,
            "profile": None,
            "xml_message_type": "pain.001.001.11",
            "xml_template_file_path": None,
            "xsd_schema_file_path": None,
            "data_file_path": "payments.csv",
            "output_dir": None,
            "streaming": False,
            "chunk_size": None,
            "emit_metrics": False,
        }
    )
    assert resolved["chunk_size"] == 42


def test_config_manager_rejects_unknown_keys(tmp_path) -> None:
    config_path = tmp_path / "pain001.yaml"
    config_path.write_text("unknown_key: value\n", encoding="utf-8")
    manager = ConfigManager()
    with pytest.raises(ValueError, match="Unknown config keys"):
        manager.load_from_file(config_path)


def test_config_manager_loads_toml_config(tmp_path) -> None:
    config_path = tmp_path / "pain001.toml"
    config_path.write_text(
        'xml_message_type = "pain.001.001.11"\nchunk_size = 10\n',
        encoding="utf-8",
    )
    loaded = ConfigManager().load_from_file(config_path)
    assert loaded["xml_message_type"] == "pain.001.001.11"
    assert loaded["chunk_size"] == 10


def test_config_manager_loads_ini_config(tmp_path) -> None:
    config_path = tmp_path / "pain001.ini"
    config_path.write_text(
        "[Paths]\n"
        "xml_template_file_path = t.xml\n"
        "xsd_schema_file_path = s.xsd\n"
        "data_file_path = d.csv\n",
        encoding="utf-8",
    )
    loaded = ConfigManager().load_from_file(config_path)
    assert loaded["xml_template_file_path"] == "t.xml"
    assert loaded["data_file_path"] == "d.csv"


def test_config_manager_rejects_unsupported_format(tmp_path) -> None:
    config_path = tmp_path / "pain001.txt"
    config_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported config format"):
        ConfigManager().load_from_file(config_path)


def test_config_manager_rejects_chunk_size_below_one(tmp_path) -> None:
    config_path = tmp_path / "pain001.yaml"
    config_path.write_text("chunk_size: 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="chunk_size must be >= 1"):
        ConfigManager().load_from_file(config_path)


def test_config_manager_rejects_non_mapping_profiles(tmp_path) -> None:
    config_path = tmp_path / "pain001.yaml"
    config_path.write_text("profiles:\n  - v12\n", encoding="utf-8")
    with pytest.raises(ValueError, match="profiles must be a mapping"):
        ConfigManager().load_from_file(config_path)


def test_config_manager_get_profile_from_presets() -> None:
    profile = ConfigManager().get_profile("sepa_direct_debit")
    assert profile["xml_message_type"] == "pain.008.001.02"


def test_config_manager_get_profile_from_project_config(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pain001.yaml").write_text(
        "profiles:\n  local:\n    xml_message_type: pain.001.001.09\n",
        encoding="utf-8",
    )
    profile = ConfigManager().get_profile("local")
    assert profile["xml_message_type"] == "pain.001.001.09"


def test_config_manager_get_profile_unknown(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(KeyError, match="Unknown profile"):
        ConfigManager().get_profile("does-not-exist")


def test_config_manager_resolve_unknown_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(KeyError, match="Unknown profile"):
        ConfigManager().resolve({"profile": "does-not-exist"})


def test_config_manager_resolve_with_explicit_config_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "custom.yaml"
    config_path.write_text(
        "xml_message_type: pain.001.001.10\n"
        "profiles:\n  extra:\n    streaming: true\n",
        encoding="utf-8",
    )
    resolved = ConfigManager().resolve({"config_file": str(config_path)})
    assert resolved["xml_message_type"] == "pain.001.001.10"


def test_config_manager_discover_user_config(tmp_path, monkeypatch) -> None:
    config_home = tmp_path / ".config" / "pain001"
    config_home.mkdir(parents=True)
    (config_home / "config.yaml").write_text(
        "chunk_size: 77\n", encoding="utf-8"
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    manager = ConfigManager()
    assert manager.discover_user_config() == config_home / "config.yaml"
    resolved = manager.resolve({})
    assert resolved["chunk_size"] == 77


def test_config_manager_env_value_coercion(monkeypatch) -> None:
    manager = ConfigManager()
    monkeypatch.setenv("PAIN001_STREAMING", "yes")
    monkeypatch.setenv("PAIN001_MESSAGE_TYPE", "pain.001.001.09")
    resolved = manager.resolve({})
    assert resolved["streaming"] is True
    assert resolved["xml_message_type"] == "pain.001.001.09"
