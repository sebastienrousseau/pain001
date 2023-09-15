import pytest
import sys
from contextlib import contextmanager
from io import StringIO
from pain001.core.core import process_files


@contextmanager
def catch_stdout():
    old_out = None  # type: StringIO
    try:
        old_out, sys.stdout = sys.stdout, StringIO()
        yield sys.stdout
    finally:
        sys.stdout = old_out


class TestProcessFiles:
    def test_invalid_csv_data(self):
        """
        Test case for processing files with invalid CSV data.
        """
        with catch_stdout():
            with pytest.raises(SystemExit) as exc_info:
                process_files(
                    "pain.001.001.03",
                    "tests/data/template.xml",
                    "tests/data/template.xsd",
                    "tests/data/invalid.csv",
                )

        assert exc_info.value.code == 1

    def test_invalid_xml_message_type(self):
        """
        Test case for processing files with an invalid XML message type.
        """
        with pytest.raises(ValueError) as exc_info:
            process_files(
                "invalid",
                "tests/data/template.xml",
                "tests/data/template.xsd",
                "tests/data/template.csv",
            )

        error_message = str(exc_info.value)
        expected_error_message = (
            "Error: Invalid XML message type: 'invalid'."
        )
        assert error_message == expected_error_message

    def test_nonexistent_data_file_path(self):
        """
        Test case for processing files with a non-existent data file path.
        """
        with pytest.raises(FileNotFoundError) as exc_info:
            process_files(
                "pain.001.001.03",
                "tests/data/template.xml",
                "tests/data/template.xsd",
                "tests/data/nonexistent.csv",
            )
        assert (
            str(exc_info.value)
            == "Error: Data file 'tests/data/nonexistent.csv' does not exist."
        )

    def test_nonexistent_xml_file_path(self):
        """
        Test case for processing files with a non-existent XML file path.
        """
        with pytest.raises(FileNotFoundError):
            process_files(
                "pain.001.001.03",
                "tests/data/nonexistent.xml",
                "tests/data/template.xsd",
                "tests/data/template.csv",
            )
        # assert exc_info.value.code == 1

    def test_nonexistent_xsd_file_path(self):
        """
        Test case for processing files with a non-existent XSD file path.
        """
        with pytest.raises(FileNotFoundError):
            process_files(
                "pain.001.001.03",
                "tests/data/template.xml",
                "tests/data/nonexistent.xsd",
                "tests/data/template.csv",
            )
        # assert exc_info.value.code == 1

    def test_successful_execution(self):
        """
        Test case for successful execution of file processing.
        """
        process_files(
            "pain.001.001.03",
            "tests/data/template.xml",
            "tests/data/template.xsd",
            "tests/data/template.csv",
        )

    def test_unsupported_data_file_type(self):
        """
        Test case for processing files with an unsupported data file type.
        """
        with pytest.raises(ValueError) as exc_info:
            process_files(
                "pain.001.001.03",
                "tests/data/template.xml",
                "tests/data/template.xsd",
                "tests/data/invalid.rtf",
            )
        assert (
            str(exc_info.value) == "Error: Unsupported data file type."
        )

    def test_uses_sqlite_database(self):
        """
        Test case for processing files using an SQLite database.
        """
        xml_message_type = "pain.001.001.03"
        xml_file_path = "tests/data/template.xml"
        xsd_file_path = "tests/data/template.xsd"
        data_file_path = "tests/data/template.db"

        process_files(
            xml_message_type,
            xml_file_path,
            xsd_file_path,
            data_file_path,
        )

    def test_valid_xml_message_type(self):
        """
        Test case for processing files with a valid XML message type.
        """
        process_files(
            "pain.001.001.03",
            "tests/data/template.xml",
            "tests/data/template.xsd",
            "tests/data/template.csv",
        )
