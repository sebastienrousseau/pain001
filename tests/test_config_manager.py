import os

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

