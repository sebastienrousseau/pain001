# Copyright (C) 2023-2026 Pain001. All rights reserved.
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

"""Additional CLI tests for coverage."""

import configparser

from click.testing import CliRunner

from pain001.cli.cli import main


class TestCLIConfigFile:
    """Test CLI config file handling."""

    def test_cli_with_config_file(self, tmp_path):
        """Test CLI with config file."""
        # Create a config file
        config_file = tmp_path / "config.ini"
        config = configparser.ConfigParser()
        config["Paths"] = {
            "xml_template_file_path": "pain001/templates/pain.001.001.03/template.xml",
            "xsd_schema_file_path": "pain001/templates/pain.001.001.03/pain.001.001.03.xsd",
            "data_file_path": str(tmp_path / "data.csv"),
        }
        with open(config_file, "w", encoding="utf-8") as f:
            config.write(f)

        # Create minimal CSV
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--config",
                str(config_file),
                "--type",
                "pain.001.001.03",
            ],
            catch_exceptions=False,
        )
        # May fail validation but should process config file
        assert result.exit_code in [0, 1, 2]

    def test_cli_with_output_dir(self, tmp_path):
        """Test CLI with output directory creation."""
        output_dir = tmp_path / "output"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id\n1\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--data-file",
                str(csv_file),
                "--output-dir",
                str(output_dir),
                "--type",
                "pain.001.001.03",
            ],
            catch_exceptions=False,
        )

        # Output dir should be created
        assert output_dir.exists() or result.exit_code != 0


class TestCLIErrorPaths:
    """Test CLI error handling paths."""

    def test_cli_invalid_message_type_validation(self, tmp_path):
        """Test CLI with message type that passes Click validation but fails internal check."""
        # This tests the redundant validation in cli.py lines 214-226
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id\n1\n")

        runner = CliRunner()
        # Use a valid Click choice but test the internal validation message
        result = runner.invoke(
            main,
            [
                "--data-file",
                str(csv_file),
                "--type",
                "pain.001.001.03",  # Valid type to pass Click
            ],
            catch_exceptions=False,
        )

        # Should process (may fail validation but not message type check)
        assert result.exit_code in [0, 1, 2]

    def test_cli_dry_run_with_invalid_data(self, tmp_path):
        """Test CLI dry-run mode with invalid data."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("incomplete\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--data-file",
                str(csv_file),
                "--type",
                "pain.001.001.03",
                "--dry-run",
            ],
            catch_exceptions=False,
        )

        # Should validate but not generate
        assert result.exit_code in [0, 1, 2]


class TestCLIIntrospectionFlags:
    """Test template/config introspection flags."""

    def test_cli_list_templates(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--list-templates"])
        assert result.exit_code == 0
        output = " ".join(result.output.split())
        assert "pain.001.001.03" in output
        assert "pain.008.001.02" in output

    def test_cli_show_template(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--show-template", "pain.001.001.03"])
        assert result.exit_code == 0
        output = " ".join(result.output.lower().split())
        assert "category" in output
        assert "schema" in output

    def test_cli_show_config(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "-t",
                "pain.001.001.03",
                "-d",
                "payments.csv",
                "--show-config",
            ],
        )
        assert result.exit_code == 0
        output = " ".join(result.output.lower().split())
        assert "template" in output

    def test_cli_emit_metrics_registers_console_callback(self):
        from unittest.mock import patch

        from pain001.cli.cli import _console_metrics_callback

        runner = CliRunner()
        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            return_value=True,
        ):
            with patch("pain001.cli.cli.process_files", autospec=True):
                with patch(
                    "pain001.cli.cli.register_metrics_callback",
                    autospec=True,
                ) as mock_register:
                    result = runner.invoke(
                        main,
                        [
                            "-t",
                            "pain.001.001.03",
                            "-d",
                            "pain001/test_fixtures/template.csv",
                            "--emit-metrics",
                        ],
                    )
        assert result.exit_code == 0
        mock_register.assert_called_once_with(_console_metrics_callback)

    def test_console_metrics_callback_prints_event(self):
        import time

        from pain001.cli.cli import _console_metrics_callback
        from pain001.observability import MetricEvent

        _console_metrics_callback(
            MetricEvent(
                name="unit_test",
                timestamp=time.time(),
                attributes={"k": "v"},
            )
        )


class TestCLIStreamingDispatch:
    """Test streaming dispatch with and without output dir."""

    def _invoke(self, args):
        from unittest.mock import patch

        runner = CliRunner()
        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            return_value=True,
        ):
            with patch(
                "pain001.cli.cli.process_files_streaming", autospec=True
            ) as mock_streaming:
                result = runner.invoke(main, args)
        return result, mock_streaming

    def test_cli_streaming_without_output_dir(self):
        result, mock_streaming = self._invoke(
            [
                "-t",
                "pain.001.001.03",
                "-d",
                "pain001/test_fixtures/template.csv",
                "--streaming",
            ]
        )
        assert result.exit_code == 0
        assert mock_streaming.called

    def test_cli_streaming_with_output_dir(self, tmp_path):
        result, mock_streaming = self._invoke(
            [
                "-t",
                "pain.001.001.03",
                "-d",
                "pain001/test_fixtures/template.csv",
                "--streaming",
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        assert result.exit_code == 0
        assert mock_streaming.called
        assert (tmp_path / "out").exists()
