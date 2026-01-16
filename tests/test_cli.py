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

import os
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pain001.cli.cli import main


class TestCliModule(unittest.TestCase):
    """Test cases for the CLI module."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

        # Create temporary test files
        self.temp_dir = tempfile.mkdtemp()

        # Create a simple XML template
        self.xml_template = os.path.join(self.temp_dir, "template.xml")
        with open(self.xml_template, "w", encoding="utf-8") as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
    <CstmrCdtTrfInitn>
        <GrpHdr>
            <MsgId>{{ id }}</MsgId>
        </GrpHdr>
    </CstmrCdtTrfInitn>
</Document>"""
            )

        # Create a simple XSD schema
        self.xsd_schema = os.path.join(self.temp_dir, "schema.xsd")
        with open(self.xsd_schema, "w", encoding="utf-8") as f:
            f.write(
                """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
           xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
    <xs:element name="Document">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="CstmrCdtTrfInitn" minOccurs="1" maxOccurs="1">
                    <xs:complexType>
                        <xs:sequence>
                            <xs:element name="GrpHdr" minOccurs="1" maxOccurs="1">
                                <xs:complexType>
                                    <xs:sequence>
                                        <xs:element name="MsgId" type="xs:string"/>
                                    </xs:sequence>
                                </xs:complexType>
                            </xs:element>
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>"""
            )

        # Create a test CSV file
        self.csv_file = os.path.join(self.temp_dir, "data.csv")
        with open(self.csv_file, "w", encoding="utf-8") as f:
            f.write(
                "id,date,nb_of_txs,initiator_name,payment_id,payment_method\n"
            )
            f.write("MSG001,2026-01-09T10:00:00,1,Test Corp,PMT001,TRF\n")

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cli_missing_xml_message_type(self) -> None:
        """Test CLI with missing XML message type."""
        result = self.runner.invoke(
            main,
            [
                "-m",
                self.xml_template,
                "-s",
                self.xsd_schema,
                "-d",
                self.csv_file,
            ],
        )
        assert (
            result.exit_code == 2
        )  # Click's exit code for missing required option
        assert (
            "required" in result.output.lower()
            or "missing" in result.output.lower()
        )

    def test_cli_missing_files(self) -> None:
        """Test CLI with non-existent file."""
        result = self.runner.invoke(
            main,
            [
                "-t",
                "pain.001.001.03",
                "-m",
                "/nonexistent/template.xml",
                "-s",
                self.xsd_schema,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2  # Click's exit code for invalid path
        assert (
            "does not exist" in result.output.lower()
            or "invalid value" in result.output.lower()
        )

    def test_cli_invalid_xml_message_type(self) -> None:
        """Test CLI with invalid XML message type."""
        result = self.runner.invoke(
            main,
            [
                "-t",
                "invalid.message.type",
                "-m",
                self.xml_template,
                "-s",
                self.xsd_schema,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2  # Click's exit code for invalid choice
        assert (
            "invalid" in result.output.lower()
            or "choice" in result.output.lower()
        )

    def test_cli_with_config_file(self) -> None:
        """Test CLI with config file."""
        config_file = os.path.join(self.temp_dir, "config.ini")
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("[Paths]\n")
            f.write(f"xml_template_file_path = {self.xml_template}\n")
            f.write(f"xsd_schema_file_path = {self.xsd_schema}\n")
            f.write(f"data_file_path = {self.csv_file}\n")

        # Mock the process_files and validate_via_xsd functions
        with patch(
            "pain001.cli.cli.process_files", autospec=True
        ) as mock_process:
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                self.runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        self.xml_template,
                        "-s",
                        self.xsd_schema,
                        "-d",
                        self.csv_file,
                        "-c",
                        config_file,
                    ],
                )
                # The CLI should process the files
                assert mock_process.called

    def test_cli_schema_validation_failure(self) -> None:
        """Test CLI when schema validation fails."""
        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            side_effect=Exception("Validation error"),
        ):
            result = self.runner.invoke(
                main,
                [
                    "-t",
                    "pain.001.001.03",
                    "-m",
                    self.xml_template,
                    "-s",
                    self.xsd_schema,
                    "-d",
                    self.csv_file,
                ],
            )
            assert result.exit_code == 1
            assert "Schema validation failed" in result.output

    def test_cli_dry_run_validates_without_generation(self) -> None:
        """Test CLI dry-run flag validates data but skips XML generation."""

        with patch(
            "pain001.cli.cli.process_files", autospec=True
        ) as mock_process:
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                with patch(
                    "pain001.cli.cli.load_payment_data",
                    autospec=True,
                    return_value=[{}],
                ) as mock_load:
                    result = self.runner.invoke(
                        main,
                        [
                            "-t",
                            "pain.001.001.03",
                            "-m",
                            self.xml_template,
                            "-s",
                            self.xsd_schema,
                            "-d",
                            self.csv_file,
                            "--dry-run",
                        ],
                    )

        assert result.exit_code == 0
        assert (
            "no XML generated" in result.output.lower()
            or "dry-run" in result.output.lower()
        )
        mock_load.assert_called_once_with(self.csv_file)
        mock_process.assert_not_called()

    def test_cli_expanduser_paths(self) -> None:
        """Test that CLI expands user paths correctly."""
        # Create a file in the temp directory
        home_xml = os.path.join(self.temp_dir, "home_template.xml")
        with open(home_xml, "w", encoding="utf-8") as f:
            f.write("<root></root>")

        with patch("os.path.expanduser", autospec=True, return_value=home_xml):
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                with patch("pain001.cli.cli.process_files", autospec=True):
                    result = self.runner.invoke(
                        main,
                        [
                            "-t",
                            "pain.001.001.03",
                            "-m",
                            "~/template.xml",
                            "-s",
                            self.xsd_schema,
                            "-d",
                            self.csv_file,
                        ],
                    )
                    # Should not fail due to path expansion
                    assert (
                        "does not exist" not in result.output
                        or result.exit_code != 1
                    )

    def test_cli_main_entry_point(self) -> None:
        """Test that CLI main entry point works."""
        import subprocess
        import sys

        # Test running cli.py directly as a script
        result = subprocess.run(
            [sys.executable, "-m", "pain001.cli.cli"],
            capture_output=True,
            text=True,
        )
        # The script should exit with error code due to missing arguments
        # but not crash with import errors
        assert result.returncode in [0, 1, 2]

    def test_cli_output_dir_creates_directory(self) -> None:
        """Test that --output-dir flag creates directory if it doesn't exist."""
        output_dir = os.path.join(self.temp_dir, "output", "xml")

        with patch("pain001.cli.cli.process_files", autospec=True):
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                result = self.runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        self.xml_template,
                        "-s",
                        self.xsd_schema,
                        "-d",
                        self.csv_file,
                        "-o",
                        output_dir,
                    ],
                )

        assert result.exit_code == 0
        assert os.path.exists(output_dir)

    def test_cli_output_dir_used_for_generation(self) -> None:
        """Test that generated files go to --output-dir."""
        output_dir = os.path.join(self.temp_dir, "custom_output")
        os.makedirs(output_dir, exist_ok=True)

        with patch("pain001.cli.cli.process_files", autospec=True):
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                result = self.runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        self.xml_template,
                        "-s",
                        self.xsd_schema,
                        "-d",
                        self.csv_file,
                        "-o",
                        output_dir,
                    ],
                )

        assert result.exit_code == 0
        assert (
            f"Output Location: {output_dir}" in result.output
            or "Success" in result.output
        )

    def test_cli_verbose_flag_enables_debug_logging(self) -> None:
        """Test that --verbose flag enables detailed logging."""
        with patch("pain001.cli.cli.process_files", autospec=True):
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                result = self.runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        self.xml_template,
                        "-s",
                        self.xsd_schema,
                        "-d",
                        self.csv_file,
                        "--verbose",
                    ],
                )

        assert "Verbose logging enabled" in result.output

    def test_cli_dry_run_with_verbose(self) -> None:
        """Test combining --dry-run and --verbose flags."""
        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            return_value=True,
        ):
            with patch(
                "pain001.cli.cli.load_payment_data",
                autospec=True,
                return_value=[{"id": "1"}, {"id": "2"}],
            ):
                result = self.runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        self.xml_template,
                        "-s",
                        self.xsd_schema,
                        "-d",
                        self.csv_file,
                        "--dry-run",
                        "--verbose",
                    ],
                )

        assert result.exit_code == 0
        assert (
            "payment records" in result.output
            or "validation passed" in result.output.lower()
        )

    def test_cli_improved_error_messages(self) -> None:
        """Test that error messages include helpful tips."""
        with patch(
            "pain001.cli.cli.validate_via_xsd",
            autospec=True,
            side_effect=Exception("Schema mismatch error"),
        ):
            result = self.runner.invoke(
                main,
                [
                    "-t",
                    "pain.001.001.03",
                    "-m",
                    self.xml_template,
                    "-s",
                    self.xsd_schema,
                    "-d",
                    self.csv_file,
                ],
            )

        assert result.exit_code == 1
        # Check for helpful tip in output
        assert (
            "Tip" in result.output
            or "validation failed" in result.output.lower()
        )

    def test_cli_required_fields_via_click(self) -> None:
        """Test that Click enforces required fields."""
        # Test missing --template
        result = self.runner.invoke(
            main,
            [
                "-t",
                "pain.001.001.03",
                "-s",
                self.xsd_schema,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2  # Click's exit code for usage errors

    def test_cli_invalid_message_type_via_click_choice(self) -> None:
        """Test that Click validates message type via Choice."""
        result = self.runner.invoke(
            main,
            [
                "-t",
                "invalid.999.999.99",
                "-m",
                self.xml_template,
                "-s",
                self.xsd_schema,
                "-d",
                self.csv_file,
            ],
        )
        assert result.exit_code == 2  # Click's exit code for invalid choice

    def test_cli_alias_flags(self) -> None:
        """Test that short and long flag names work."""
        with patch("pain001.cli.cli.process_files", autospec=True):
            with patch(
                "pain001.cli.cli.validate_via_xsd",
                autospec=True,
                return_value=True,
            ):
                # Test short flags
                result_short = self.runner.invoke(
                    main,
                    [
                        "-t",
                        "pain.001.001.03",
                        "-m",
                        self.xml_template,
                        "-s",
                        self.xsd_schema,
                        "-d",
                        self.csv_file,
                        "-v",  # Short verbose flag
                    ],
                )

                # Test long flags
                result_long = self.runner.invoke(
                    main,
                    [
                        "--xml-message-type",
                        "pain.001.001.03",
                        "--template",
                        self.xml_template,
                        "--schema",
                        self.xsd_schema,
                        "--data",
                        self.csv_file,
                        "--verbose",
                    ],
                )

        assert result_short.exit_code == 0
        assert result_long.exit_code == 0


if __name__ == "__main__":
    unittest.main()
