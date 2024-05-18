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
        with pytest.raises(SystemExit) as exc_info:
            process_files(
                "pain.001.001.03",
                "tests/data/template.xml",
                "tests/data/template.xsd",
                "tests/data/invalid.csv",
            )
        assert exc_info.type == SystemExit
        assert exc_info.value.code == 1

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
