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
        from unittest.mock import patch

        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            return_value=True,
        ):
            with patch("pain001.cli.cli.process_files", autospec=True):
                result = self.runner.invoke(
                    cli,
                    [
                        "-t",
                        self.xml_message_type,
                        "-m",
                        self.xml_file,
                        "-s",
                        self.xsd_file,
                        "-d",
                        self.csv_file,
                    ],
                )
        assert result.exit_code == 0

    def test_main_with_missing_xml_message_type(self) -> None:
        """Click enforces required options — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-m",
                self.xml_file,
                "-s",
                self.xsd_file,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2
        assert (
            "required" in result.output.lower()
            or "missing" in result.output.lower()
        )

    def test_main_with_missing_template(self) -> None:
        """Click enforces required --template option — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                self.xml_message_type,
                "-s",
                self.xsd_file,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2
        assert (
            "required" in result.output.lower()
            or "missing" in result.output.lower()
        )

    def test_main_with_missing_schema(self) -> None:
        """Click enforces required --schema option — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                self.xml_message_type,
                "-m",
                self.xml_file,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2
        assert (
            "required" in result.output.lower()
            or "missing" in result.output.lower()
        )

    def test_main_with_missing_data(self) -> None:
        """Click enforces required --data option — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                self.xml_message_type,
                "-m",
                self.xml_file,
                "-s",
                self.xsd_file,
            ],
        )
        assert result.exit_code == 2
        assert (
            "required" in result.output.lower()
            or "missing" in result.output.lower()
        )

    def test_main_with_invalid_xml_message_type(self) -> None:
        """Click.Choice validates message type — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                "invalid",
                "-m",
                self.xml_file,
                "-s",
                self.xsd_file,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2
        assert (
            "invalid" in result.output.lower()
            or "choice" in result.output.lower()
        )

    def test_main_with_nonexistent_template_file(self) -> None:
        """Click.Path(exists=True) rejects non-existent files — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                self.xml_message_type,
                "-m",
                "nonexistent.xml",
                "-s",
                self.xsd_file,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2
        assert "does not exist" in result.output.lower()

    def test_main_with_nonexistent_schema_file(self) -> None:
        """Click.Path(exists=True) rejects non-existent files — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                self.xml_message_type,
                "-m",
                self.xml_file,
                "-s",
                "nonexistent.xsd",
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2
        assert "does not exist" in result.output.lower()

    def test_main_with_nonexistent_data_file(self) -> None:
        """Click.Path(exists=True) rejects non-existent files — exit code 2."""
        result = self.runner.invoke(
            cli,
            [
                "-t",
                self.xml_message_type,
                "-m",
                self.xml_file,
                "-s",
                self.xsd_file,
                "-d",
                "nonexistent.csv",
            ],
        )
        assert result.exit_code == 2
        assert "does not exist" in result.output.lower()

    def test_main_with_exception_handling(self) -> None:
        """Test CLI exception handling via schema validation failure."""
        from unittest.mock import patch

        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            side_effect=Exception("Test exception"),
        ):
            result = self.runner.invoke(
                cli,
                [
                    "-t",
                    self.xml_message_type,
                    "-m",
                    self.xml_file,
                    "-s",
                    self.xsd_file,
                    "-d",
                    self.csv_file,
                ],
            )
            assert result.exit_code == 1
            assert "validation failed" in result.output.lower()

    def test_main_module_entry_point(self) -> None:
        """Test __main__.py when run as a script."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pain001.__main__", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout or "Options:" in result.stdout
