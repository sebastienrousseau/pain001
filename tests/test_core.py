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
        with pytest.raises(ValueError) as exc_info:
            process_files(
                "pain.001.001.03",
                "tests/data/template.xml",
                "tests/data/template.xsd",
                "tests/data/invalid.csv",
            )
        assert (
            str(exc_info.value)
            == "The CSV file 'tests/data/invalid.csv' is empty."
        )

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
