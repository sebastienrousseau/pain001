"""Edge-branch regression tests for CLI and core helpers."""

import xml.etree.ElementTree as et  # nosec B405 - only used for element creation in tests, not parsing
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.cli.cli import main as cli_main
from pain001.core import core
from pain001.csv.validate_csv_data import _validate_field_type
from pain001.exceptions import XMLGenerationError
from pain001.xml.write_xml_to_file import write_xml_to_file


def test_cli_missing_data_file_exits(tmp_path: Path) -> None:
    """Ensure CLI exits when a required file is missing."""
    template = tmp_path / "template.xml"
    schema = tmp_path / "schema.xsd"
    template.write_text("<xml></xml>", encoding="utf-8")
    schema.write_text("<xsd></xsd>", encoding="utf-8")
    missing_data = tmp_path / "missing.csv"

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "-t",
            "pain.001.001.03",
            "-m",
            str(template),
            "-s",
            str(schema),
            "-d",
            str(missing_data),
        ],
    )

    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_process_files_invalid_message_type(tmp_path: Path) -> None:
    """process_files raises ValueError for unsupported message type."""
    template = tmp_path / "template.xml"
    schema = tmp_path / "schema.xsd"
    template.write_text("<xml></xml>", encoding="utf-8")
    schema.write_text("<xsd></xsd>", encoding="utf-8")

    with pytest.raises(XMLGenerationError):
        core.process_files("invalid.type", str(template), str(schema), [])


def test_process_files_missing_template(tmp_path: Path) -> None:
    """process_files raises when template path is missing."""
    missing_template = tmp_path / "no-template.xml"
    schema = tmp_path / "schema.xsd"
    schema.write_text("<xsd></xsd>", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        core.process_files(
            "pain.001.001.03", str(missing_template), str(schema), []
        )


def test_process_files_missing_schema(tmp_path: Path) -> None:
    """process_files raises when schema path is missing."""
    template = tmp_path / "template.xml"
    template.write_text("<xml></xml>", encoding="utf-8")
    missing_schema = tmp_path / "no-schema.xsd"

    with pytest.raises(FileNotFoundError):
        core.process_files(
            "pain.001.001.03", str(template), str(missing_schema), []
        )


def test_process_files_missing_output_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover branch where output file is reported missing after generation."""

    # Mock validate_path to always succeed (pass-through)
    monkeypatch.setattr(core, "validate_path", lambda p, **kwargs: Path(p))

    # Mock os.path.exists to return False (simulating output file check failure)
    monkeypatch.setattr(core.os.path, "exists", lambda _path: False)

    monkeypatch.setattr(core, "_load_data", lambda _path, _start: [])
    monkeypatch.setattr(core, "_register_message_namespaces", lambda _t: None)
    monkeypatch.setattr(core, "_generate_and_log", lambda *_args, **_kwargs: 0)

    core.process_files("pain.001.001.03", "template.xml", "schema.xsd", [])


def test_validate_field_type_boolean_branch() -> None:
    """Validate boolean branch covers true/false validation."""
    assert _validate_field_type("true", bool) is True
    assert _validate_field_type("FALSE", bool) is True
    assert _validate_field_type("not-bool", bool) is False


def test_write_xml_to_file_indentation(tmp_path: Path) -> None:
    """Ensure write_xml_to_file indents child elements."""
    root = et.Element("root")
    child = et.Element("child")
    root.append(child)

    xml_path = tmp_path / "output.xml"
    write_xml_to_file(str(xml_path), root)

    content = xml_path.read_text(encoding="utf-8")
    assert "<root>" in content
    assert "\n  <child />" in content
