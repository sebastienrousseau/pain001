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

"""Error-path tests for the data loaders and validators."""

import pytest

from pain001.data.loader import load_payment_data, load_payment_data_streaming
from pain001.exceptions import DataSourceError
from pain001.json.load_json_data import load_json_data, load_jsonl_data


class TestJsonErrors:
    """Error and edge cases for the JSON / JSONL loaders."""

    def test_invalid_json_raises(self, tmp_path) -> None:
        """Malformed JSON raises DataSourceError."""
        f = tmp_path / "bad.json"
        f.write_text("{ not valid json")
        with pytest.raises(DataSourceError):
            load_json_data(str(f))

    def test_scalar_root_raises(self, tmp_path) -> None:
        """A JSON scalar (not object/array) raises DataSourceError."""
        f = tmp_path / "scalar.json"
        f.write_text("42")
        with pytest.raises(DataSourceError):
            load_json_data(str(f))

    def test_array_with_non_dict_raises(self, tmp_path) -> None:
        """A JSON array of non-objects raises DataSourceError."""
        f = tmp_path / "arr.json"
        f.write_text("[1, 2, 3]")
        with pytest.raises(DataSourceError):
            load_json_data(str(f))

    def test_single_object_is_wrapped(self, tmp_path) -> None:
        """A single JSON object is returned as a one-row list."""
        f = tmp_path / "obj.json"
        f.write_text('{"id": "1"}')
        assert load_json_data(str(f)) == [{"id": "1"}]

    def test_jsonl_invalid_line_raises(self, tmp_path) -> None:
        """A malformed JSONL line raises DataSourceError."""
        f = tmp_path / "bad.jsonl"
        f.write_text('{"id": "1"}\n{ broken\n')
        with pytest.raises(DataSourceError):
            load_jsonl_data(str(f))

    def test_jsonl_non_dict_line_raises(self, tmp_path) -> None:
        """A non-object JSONL line raises DataSourceError."""
        f = tmp_path / "nondict.jsonl"
        f.write_text("123\n")
        with pytest.raises(DataSourceError):
            load_jsonl_data(str(f))

    def test_jsonl_empty_raises(self, tmp_path) -> None:
        """An empty JSONL file raises DataSourceError."""
        f = tmp_path / "empty.jsonl"
        f.write_text("\n\n")
        with pytest.raises(DataSourceError):
            load_jsonl_data(str(f))


class TestLoaderDispatchErrors:
    """Error paths in the unified data loader dispatch."""

    def test_unsupported_extension_raises(self, tmp_path) -> None:
        """An unknown file extension raises DataSourceError."""
        f = tmp_path / "data.txt"
        f.write_text("id\n1\n")
        with pytest.raises(DataSourceError):
            load_payment_data(str(f))

    def test_streaming_unsupported_type_raises(self) -> None:
        """A non-str/list streaming source raises DataSourceError."""
        with pytest.raises(DataSourceError):
            list(load_payment_data_streaming(123))  # type: ignore[arg-type]

    def test_streaming_empty_list_raises(self) -> None:
        """An empty list streaming source raises DataSourceError."""
        with pytest.raises(DataSourceError):
            list(load_payment_data_streaming([]))

    def test_streaming_unsupported_extension_raises(self, tmp_path) -> None:
        """An unknown extension in streaming mode raises DataSourceError."""
        f = tmp_path / "data.txt"
        f.write_text("id\n1\n")
        with pytest.raises(DataSourceError):
            list(load_payment_data_streaming(str(f)))


class TestOtherLoaderErrors:
    """Error paths in the CSV, DB, and camt.053 readers."""

    def test_csv_file_not_found(self) -> None:
        """A missing CSV path raises FileNotFoundError."""
        from pain001.csv.load_csv_data import load_csv_data

        with pytest.raises(FileNotFoundError):
            load_csv_data("definitely_missing_file.csv")

    def test_db_validation_rejects_missing_columns(self) -> None:
        """A row missing required columns fails DB validation."""
        from pain001.db.validate_db_data import validate_db_data

        assert validate_db_data([{"id": "1"}]) is False

    def test_camt053_parse_error(self, tmp_path) -> None:
        """A non-XML file raises DataSourceError from the camt.053 parser."""
        from pain001.camt053 import parse_camt053_statement

        f = tmp_path / "bad.xml"
        f.write_text("this is not xml")
        with pytest.raises(DataSourceError):
            parse_camt053_statement(str(f))

    def test_jsonl_streaming_bad_line(self, tmp_path) -> None:
        """A malformed line aborts JSONL streaming with DataSourceError."""
        from pain001.json.load_json_data import load_jsonl_data_streaming

        f = tmp_path / "stream.jsonl"
        f.write_text('{"id": "1"}\n{ broken\n')
        with pytest.raises(DataSourceError):
            list(load_jsonl_data_streaming(str(f), chunk_size=1))


class TestValidationResponseComputation:
    """The ValidationResponse invalid_rows field is derived."""

    def test_invalid_rows_is_computed(self) -> None:
        """Providing invalid_rows triggers recomputation: total - valid.

        (Pydantic v2 only runs the field validator when the field is
        supplied, not for its default — so pass it explicitly.)
        """
        from pain001.api.models import ValidationResponse

        response = ValidationResponse(
            is_valid=False, total_rows=10, valid_rows=7, invalid_rows=0
        )
        assert response.invalid_rows == 3
