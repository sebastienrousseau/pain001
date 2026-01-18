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

import re
from pathlib import Path

from click.testing import CliRunner

from pain001.__main__ import cli


class TestMain:
    def setup_method(self) -> None:
        self.runner = CliRunner()
        self.xml_message_type = "pain.001.001.03"
        self.xml_file = "pain001/test_fixtures/template.xml"
        self.xsd_file = "pain001/test_fixtures/template.xsd"
        self.csv_file = "pain001/test_fixtures/template.csv"

    def test_main_with_valid_files(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xml_template_file_path",
                self.xml_file,
                "--xsd_schema_file_path",
                self.xsd_file,
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 0
        resolved_xsd = Path(self.xsd_file).resolve()
        assert (
            f"The XML has been validated against `{resolved_xsd}`"
            in result.output
        )

    def test_main_with_missing_xml_message_type(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_template_file_path",
                self.xml_file,
                "--xsd_schema_file_path",
                self.xsd_file,
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 1
        assert "The XML message type is required." in result.output

    def test_main_with_missing_xsd_template_file(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xml_template_file_path",
                self.xml_file,
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 1
        assert "The XSD schema file path is required." in result.output

    def test_main_with_missing_data_file(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xml_template_file_path",
                self.xml_file,
                "--xsd_schema_file_path",
                self.xsd_file,
            ],
        )
        assert result.exit_code == 1
        assert "The data file path is required." in result.output

    def test_main_with_invalid_xml_message_type(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                "invalid",
                "--xml_template_file_path",
                self.xml_file,
                "--xsd_schema_file_path",
                self.xsd_file,
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 1
        # Strip ANSI color codes before assertion
        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "Invalid XML message type: invalid" in clean_output

    def test_main_with_invalid_xml_template_file(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xml_template_file_path",
                "invalid",
                "--xsd_schema_file_path",
                self.xsd_file,
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 1
        # Strip ANSI color codes before assertion
        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "XML template file does not exist: invalid" in clean_output

    def test_main_with_invalid_xsd_template_file(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xml_template_file_path",
                self.xml_file,
                "--xsd_schema_file_path",
                "invalid",
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 1
        # Strip ANSI color codes before assertion
        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "XSD schema file does not exist: invalid" in clean_output

    def test_main_with_invalid_data_file(self) -> None:
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xml_template_file_path",
                self.xml_file,
                "--xsd_schema_file_path",
                self.xsd_file,
                "--data_file_path",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        # Strip ANSI color codes before assertion
        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "Data file does not exist: invalid" in clean_output

    def test_main_with_missing_xml_template_file_path(self) -> None:
        """Test CLI when XML template file path is missing."""
        result = self.runner.invoke(
            cli,
            [
                "--xml_message_type",
                self.xml_message_type,
                "--xsd_schema_file_path",
                self.xsd_file,
                "--data_file_path",
                self.csv_file,
            ],
        )
        assert result.exit_code == 1
        assert "The XML template file path is required." in result.output

    def test_main_with_exception_handling(self) -> None:
        """Test CLI exception handling."""
        from unittest.mock import patch

        # We need to mock it in the __main__ module where it's imported
        with patch(
            "pain001.__main__.process_files",
            autospec=True,
            side_effect=Exception("Test exception"),
        ):
            result = self.runner.invoke(
                cli,
                [
                    "--xml_message_type",
                    self.xml_message_type,
                    "--xml_template_file_path",
                    self.xml_file,
                    "--xsd_schema_file_path",
                    self.xsd_file,
                    "--data_file_path",
                    self.csv_file,
                ],
            )
            assert result.exit_code == 1
            assert "An error occurred: Test exception" in result.output

    def test_main_module_entry_point(self) -> None:
        """Test __main__.py when run as a script."""
        import subprocess
        import sys

        # Test running __main__.py directly as a module
        result = subprocess.run(
            [sys.executable, "-m", "pain001.__main__", "--help"],
            capture_output=True,
            text=True,
        )
        # Should show help without error
        assert result.returncode == 0
        assert "Usage:" in result.stdout or "Options:" in result.stdout
