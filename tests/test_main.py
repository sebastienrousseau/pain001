import io
import pytest
import sys
from pain001.__main__ import main
from unittest.mock import patch


class TestMain:

    def setup_method(self):
        self.xml_file = "tests/data/template.xml"
        self.xsd_file = "tests/data/template.xsd"
        self.csv_file = "tests/data/template.csv"

    def test_main_with_valid_files(self):
        with patch.object(
            sys,
            'argv',
            ['', self.xml_file, self.xsd_file, self.csv_file]
        ):
            with patch(
                'sys.stdout', new_callable=io.StringIO
            ) as captured_output:
                main(self.xml_file, self.xsd_file, self.csv_file)

            captured_text = captured_output.getvalue()
            assert (
                "❯ XML located at "
                "tests/data/template_updated.xml "
                "is valid."
                in captured_text
            )

    def test_main_with_invalid_xml_file(self):
        with patch.object(sys, 'argv', [
            '', 'tests/data/invalid.xml', self.xsd_file, self.csv_file
        ]):
            with patch(
                'sys.stdout', new_callable=io.StringIO
            ) as captured_output:
                with pytest.raises(SystemExit):
                    main(
                        'tests/data/invalid.xml',
                        self.xsd_file,
                        self.csv_file
                    )

            assert (
                "The XML template "
                "file does not exist."
                in captured_output.getvalue()
            )

    def test_main_with_invalid_xsd_file(self):
        with patch.object(
            sys, 'argv', [
                '',
                self.xml_file,
                'tests/data/invalid.xsd',
                self.csv_file
            ]
        ):
            with patch(
                'sys.stdout',
                new_callable=io.StringIO
            ) as captured_output:
                with pytest.raises(SystemExit):
                    main(
                        self.xml_file,
                        'tests/data/invalid.xsd',
                        self.csv_file
                    )

            assert (
                "The XSD template file does not exist."
                in captured_output.getvalue()
            )

    def test_main_with_invalid_csv_file(self):
        with patch.object(
            sys,
            'argv',
            [
                '',
                self.xml_file,
                self.xsd_file,
                'tests/data/invalid.csv'
            ]
        ):
            with patch(
                'sys.stdout',
                new_callable=io.StringIO
            ) as captured_output:
                with pytest.raises(SystemExit):
                    main(
                        self.xml_file,
                        self.xsd_file,
                        'tests/data/invalid.csv'
                    )

        assert (
            "The CSV file 'tests/data/invalid.csv' does not exist."
            in captured_output.getvalue()
        )

    def test_main_with_file_not_found_error(self):
        with patch.object(
            sys,
            'argv',
            ['',
             self.xml_file,
             self.xsd_file,
             'tests/data/file_not_found.csv'
             ]
        ):
            with patch(
                'sys.stdout',
                new_callable=io.StringIO
            ) as captured_output:
                with pytest.raises(SystemExit):
                    main(self.xml_file, self.xsd_file,
                         'tests/data/file_not_found.csv')

            assert (
                "CSV file "
                "'tests/data/file_not_found.csv' "
                "does not exist."
                in captured_output.getvalue()
            )
