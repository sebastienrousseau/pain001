import io
import pytest
import sys
from pain001.__main__ import main
from unittest.mock import patch


class TestMain:
    def setup_method(self):
        self.xml_message_type = "pain.001.001.03"
        self.xml_file = "tests/data/template.xml"
        self.xsd_file = "tests/data/template.xsd"
        self.csv_file = "tests/data/template.csv"
        self.output_file = "tests/data/output.xml"

    def test_main_with_valid_files(self):
        with patch.object(
            sys,
            "argv",
            [
                "",
                self.xml_message_type,
                self.xml_file,
                self.xsd_file,
                self.csv_file,
                self.output_file,
            ],
        ):
            with patch(
                "sys.stdout", new_callable=io.StringIO
            ) as captured_output:
                main()
            assert (
                "❯ XML located at tests/data/pain.001.001.03.xml is valid."
                in captured_output.getvalue()
            )

    def test_main_with_invalid_csv_file(self):
        with patch.object(
            sys,
            "argv",
            [
                "",
                self.xml_message_type,
                self.xml_file,
                self.xsd_file,
                "tests/data/invalid.csv",
                self.output_file,
            ],
        ):
            with patch(
                "sys.stdout", new_callable=io.StringIO
            ) as captured_output:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.type == SystemExit
        assert exc_info.value.code == 1
        expected_error_message = "Error: No data to process."
        assert expected_error_message in captured_output.getvalue()

    def test_main_with_invalid_xml_file(self):
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(
                sys,
                "argv",
                [
                    "",
                    self.xml_message_type,
                    "tests/data/invalid.xml",
                    self.xsd_file,
                    self.csv_file,
                    self.output_file,
                ],
            ):
                main()

        assert exc_info.type == SystemExit
        assert exc_info.value.code == 1
