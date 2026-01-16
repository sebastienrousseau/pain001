# Copyright (C) 2023 Sebastien Rousseau.
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
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test coverage gaps - CLI error paths and edge cases."""

import logging
import os
import tempfile
from xml.etree import (
    ElementTree,  # nosec B405 - Only element creation, not parsing
)

import pytest
from click.testing import CliRunner

from pain001.cli.cli import main
from pain001.context.context import Context
from pain001.xml.write_xml_to_file import write_xml_to_file


class TestCliErrorPaths:
    """Test CLI error handling paths."""

    def test_cli_missing_message_type(self) -> None:
        """Test CLI when xml_message_type is not provided."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy files so they exist
            template_path = os.path.join(tmpdir, "template.xml")
            schema_path = os.path.join(tmpdir, "schema.xsd")
            data_path = os.path.join(tmpdir, "data.csv")

            for p in [template_path, schema_path, data_path]:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("dummy")

            result = runner.invoke(
                main,
                [
                    "-m",
                    template_path,
                    "-s",
                    schema_path,
                    "-d",
                    data_path,
                ],
            )
            assert result.exit_code == 2
            assert (
                "Missing option '-t'" in result.output
                or "Missing option" in result.output
            )

    def test_cli_missing_template_path(self) -> None:
        """Test CLI when xml_template_file_path is not provided."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = os.path.join(tmpdir, "schema.xsd")
            data_path = os.path.join(tmpdir, "data.csv")

            for p in [schema_path, data_path]:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("dummy")

            result = runner.invoke(
                main,
                [
                    "-t",
                    "pain.001.001.03",
                    "-s",
                    schema_path,
                    "-d",
                    data_path,
                ],
            )
            assert result.exit_code == 2
            assert (
                "Missing option '-m'" in result.output
                or "Missing option" in result.output
            )

    def test_cli_missing_schema_path(self) -> None:
        """Test CLI when xsd_schema_file_path is not provided."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.xml")
            data_path = os.path.join(tmpdir, "data.csv")

            for p in [template_path, data_path]:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("dummy")

            result = runner.invoke(
                main,
                [
                    "-t",
                    "pain.001.001.03",
                    "-m",
                    template_path,
                    "-d",
                    data_path,
                ],
            )
            assert result.exit_code == 2
            assert (
                "Missing option '-s'" in result.output
                or "Missing option" in result.output
            )

    def test_cli_missing_data_path(self) -> None:
        """Test CLI when data_file_path is not provided."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.xml")
            schema_path = os.path.join(tmpdir, "schema.xsd")

            for p in [template_path, schema_path]:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("dummy")

            result = runner.invoke(
                main,
                [
                    "-t",
                    "pain.001.001.03",
                    "-m",
                    template_path,
                    "-s",
                    schema_path,
                ],
            )
            assert result.exit_code == 2
            assert (
                "Missing option '-d'" in result.output
                or "Missing option" in result.output
            )

    def test_cli_nonexistent_files(self) -> None:
        """Test CLI when provided files don't exist."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "-t",
                "pain.001.001.03",
                "-m",
                "/nonexistent/template.xml",
                "-s",
                "/nonexistent/schema.xsd",
                "-d",
                "/nonexistent/data.csv",
            ],
        )
        assert result.exit_code == 2
        assert "does not exist" in result.output

    def test_cli_dry_run_data_validation_failure(self) -> None:
        """Test CLI dry-run when data validation fails."""

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.xml")
            schema_path = os.path.join(tmpdir, "schema.xsd")
            data_path = os.path.join(tmpdir, "data.csv")

            for path in [template_path, schema_path, data_path]:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("content")

            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(
                    "pain001.cli.cli.validate_via_xsd",
                    lambda *args, **kwargs: True,
                    raising=False,
                )

                def _raise_value_error(*_args, **_kwargs):
                    raise ValueError("invalid data")

                mp.setattr(
                    "pain001.cli.cli.load_payment_data",
                    _raise_value_error,
                )

                result = runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        template_path,
                        "-s",
                        schema_path,
                        "-d",
                        data_path,
                        "--dry-run",
                    ],
                )

            assert result.exit_code == 1
            assert "Data validation failed" in result.output


class TestXmlWriterEdgeCases:
    """Test XML writer indentation edge cases."""

    def test_write_xml_preserves_indentation(self) -> None:
        """Test that write_xml_to_file properly indents XML elements.

        Note: ElementTree is safe here as we're creating XML elements,
        not parsing untrusted input. Only use defusedxml for parsing.
        """
        # Create a simple XML tree (element creation is safe)
        root = ElementTree.Element("root")
        child1 = ElementTree.SubElement(root, "child1")
        child1.text = "value1"
        child2 = ElementTree.SubElement(root, "child2")
        child2.text = "value2"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.xml")
            write_xml_to_file(output_path, root)

            # Verify file exists and has content
            assert os.path.exists(output_path)
            with open(output_path, encoding="utf-8") as f:
                content = f.read()
                assert "<?xml version" in content
                assert "root" in content
                assert "child1" in content
                # Check for indentation
                assert "\n" in content

    def test_write_xml_creates_file(self) -> None:
        """Test that write_xml_to_file creates the output file.

        Note: ElementTree is safe here as we're creating XML elements,
        not parsing untrusted input. Only use defusedxml for parsing.
        """
        root = ElementTree.Element("test")
        root.text = "content"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "output.xml")
            write_xml_to_file(output_path, root)

            assert os.path.exists(output_path)
            assert os.path.isfile(output_path)


class TestContextLoggerEdgeCases:
    """Test Context logger edge cases."""

    def test_context_logger_configuration(self) -> None:
        """Test context logger configuration."""
        # Get the singleton instance
        context = Context.get_instance()

        # Set a log level
        context.set_log_level("WARNING")
        assert context.log_level == logging.WARNING

        # Verify logger is configured
        logger = context.get_logger()
        assert logger is not None
        assert logger.level == logging.WARNING

    def test_context_invalid_log_level(self) -> None:
        """Test setting an invalid log level raises ValueError."""
        context = Context.get_instance()
        with pytest.raises(ValueError, match="Invalid log level"):
            context.set_log_level("INVALID_LEVEL")
