# Copyright (C) 2023-2024 Sebastien Rousseau.
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
    def setup_method(self):
        self.runner = CliRunner()
        self.xml_message_type = "pain.001.001.03"
        self.xml_file = "tests/data/template.xml"
        self.xsd_file = "tests/data/template.xsd"
        self.csv_file = "tests/data/template.csv"

    def test_main_with_valid_files(self):
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
        assert (
            "The XML has been validated against `tests/data/template.xsd`"
            in result.output
        )

    def test_main_with_missing_xml_message_type(self):
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

    def test_main_with_missing_xsd_template_file(self):
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

    def test_main_with_missing_data_file(self):
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

    def test_main_with_invalid_xml_message_type(self):
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
        assert "Invalid XML message type: invalid." in result.output

    def test_main_with_invalid_xml_template_file(self):
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
        assert (
            "The XML template file 'invalid' does not exist." in result.output
        )

    def test_main_with_invalid_xsd_template_file(self):
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
        assert (
            "The XSD template file 'invalid' does not exist." in result.output
        )

    def test_main_with_invalid_data_file(self):
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
        assert "The data file 'invalid' does not exist." in result.output
