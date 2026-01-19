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
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Comprehensive tests for JSON and JSONL data loaders.

Tests both load_json_data and load_jsonl_data functions along with
their streaming variants (load_json_data_streaming, load_jsonl_data_streaming).
"""

import json

import pytest

from pain001.exceptions import DataSourceError
from pain001.json.load_json_data import (
    load_json_data,
    load_json_data_streaming,
    load_jsonl_data,
    load_jsonl_data_streaming,
)


@pytest.fixture(name="payment_input_data")
def fixture_payment_input_data():
    """Sample payment data for testing."""
    return [
        {
            "id": "MSG001",
            "creditor_name": "Alice Corp",
            "creditor_iban": "GB33BUKB20201555555555",
            "creditor_bic": "BUKBGB22",
            "amount": "1000.00",
            "currency": "GBP",
            "payment_date": "2025-01-15",
            "debtor_name": "Bob Industries",
            "debtor_iban": "FR1420041010050500013M02606",
            "debtor_bic": "BNPAFRPP",
        },
        {
            "id": "MSG002",
            "creditor_name": "Charlie Ltd",
            "creditor_iban": "DE89370400440532013000",
            "creditor_bic": "COBADEFF",
            "amount": "500.50",
            "currency": "EUR",
            "payment_date": "2025-01-16",
            "debtor_name": "Bob Industries",
            "debtor_iban": "FR1420041010050500013M02606",
            "debtor_bic": "BNPAFRPP",
        },
    ]


@pytest.fixture(name="json_array_file")
def fixture_json_array_file(payment_input_data, tmp_path):
    """Create a temporary JSON file with array format."""
    json_file = tmp_path / "payments.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(payment_input_data, f, indent=2)
    return str(json_file)


@pytest.fixture(name="json_single_object_file")
def fixture_json_single_object_file(payment_input_data, tmp_path):
    """Create a temporary JSON file with single object."""
    json_file = tmp_path / "payment.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(payment_input_data[0], f, indent=2)
    return str(json_file)


@pytest.fixture(name="jsonl_file")
def fixture_jsonl_file(payment_input_data, tmp_path):
    """Create a temporary JSONL file."""
    jsonl_file = tmp_path / "payments.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for record in payment_input_data:
            f.write(json.dumps(record) + "\n")
    return str(jsonl_file)


@pytest.fixture(name="large_jsonl_file")
def fixture_large_jsonl_file(tmp_path):
    """Create a large JSONL file for streaming tests (5000 records)."""
    jsonl_file = tmp_path / "large_payments.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for i in range(5000):
            record = {
                "id": f"MSG{i:05d}",
                "creditor_name": f"Creditor {i}",
                "creditor_iban": "GB33BUKB20201555555555",
                "creditor_bic": "BUKBGB22",
                "amount": f"{1000 + i}.00",
                "currency": "GBP",
                "payment_date": "2025-01-15",
                "debtor_name": f"Debtor {i}",
                "debtor_iban": "FR1420041010050500013M02606",
                "debtor_bic": "BNPAFRPP",
            }
            f.write(json.dumps(record) + "\n")
    return str(jsonl_file)


# =============================================================================
# load_json_data Tests
# =============================================================================


# noqa: F811
# noqa: F811
def test_load_json_data_array_format(json_array_file, payment_input_data):
    """Test loading JSON file with array format."""
    payment_data = load_json_data(json_array_file)

    assert isinstance(payment_data, list)
    assert len(payment_data) == 2
    assert payment_data == payment_input_data
    assert payment_data[0]["id"] == "MSG001"
    assert payment_data[1]["amount"] == "500.50"


def test_load_json_data_single_object(
    json_single_object_file, payment_input_data
):
    """Test loading JSON file with single object (converts to list)."""
    payment_data = load_json_data(json_single_object_file)

    assert isinstance(payment_data, list)
    assert len(payment_data) == 1
    assert payment_data[0] == payment_input_data[0]
    assert payment_data[0]["id"] == "MSG001"


def test_load_json_data_file_not_found():
    """Test FileNotFoundError for nonexistent JSON file."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_json_data("/nonexistent/path/payments.json")

    assert "not found" in str(exc_info.value).lower()


def test_load_json_data_invalid_json(tmp_path):
    """Test DataSourceError for malformed JSON."""
    invalid_json_file = tmp_path / "invalid.json"
    with open(invalid_json_file, "w", encoding="utf-8") as f:
        f.write("{invalid json content")

    with pytest.raises(DataSourceError) as exc_info:
        load_json_data(str(invalid_json_file))

    assert "Invalid JSON" in str(exc_info.value)


def test_load_json_data_empty_file(tmp_path):
    """Test DataSourceError for empty JSON file."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")

    with pytest.raises(DataSourceError) as exc_info:
        load_json_data(str(empty_file))

    assert "Invalid JSON" in str(exc_info.value)


def test_load_json_data_non_dict_list(tmp_path):
    """Test DataSourceError for JSON containing non-dict items."""
    invalid_data_file = tmp_path / "invalid_data.json"
    with open(invalid_data_file, "w", encoding="utf-8") as f:
        json.dump(["string1", "string2", 123], f)

    with pytest.raises(DataSourceError) as exc_info:
        load_json_data(str(invalid_data_file))

    assert "must contain only objects" in str(exc_info.value)


# =============================================================================
# load_json_data_streaming Tests
# =============================================================================


def test_load_json_data_streaming_chunks(json_array_file):
    """Test streaming JSON data in chunks."""
    chunks = list(load_json_data_streaming(json_array_file, chunk_size=1))

    assert len(chunks) == 2  # 2 records, chunk_size=1
    assert all(isinstance(chunk, list) for chunk in chunks)
    assert len(chunks[0]) == 1
    assert chunks[0][0]["id"] == "MSG001"
    assert chunks[1][0]["id"] == "MSG002"


def test_load_json_data_streaming_large_chunk(json_array_file):
    """Test streaming with chunk_size larger than data."""
    chunks = list(load_json_data_streaming(json_array_file, chunk_size=10))

    assert len(chunks) == 1  # All data in one chunk
    assert len(chunks[0]) == 2


def test_load_json_data_streaming_default_chunk_size(json_array_file):
    """Test streaming with default chunk_size (1000)."""
    chunks = list(load_json_data_streaming(json_array_file))

    assert len(chunks) == 1  # 2 records, chunk_size=1000
    assert len(chunks[0]) == 2


def test_load_json_data_streaming_file_not_found():
    """Test FileNotFoundError in streaming mode."""
    with pytest.raises(FileNotFoundError):
        list(load_json_data_streaming("/nonexistent/file.json"))


# =============================================================================
# load_jsonl_data Tests
# =============================================================================


def test_load_jsonl_data_basic(jsonl_file, payment_input_data):
    """Test loading basic JSONL file."""
    payment_data = load_jsonl_data(jsonl_file)

    assert isinstance(payment_data, list)
    assert len(payment_data) == 2
    assert payment_data == payment_input_data


def test_load_jsonl_data_file_not_found():
    """Test FileNotFoundError for nonexistent JSONL file."""
    with pytest.raises(FileNotFoundError) as exc_info:
        load_jsonl_data("/nonexistent/path/payments.jsonl")

    assert "not found" in str(exc_info.value).lower()


def test_load_jsonl_data_invalid_line(tmp_path):
    """Test DataSourceError for malformed JSONL line."""
    invalid_jsonl = tmp_path / "invalid.jsonl"
    with open(invalid_jsonl, "w", encoding="utf-8") as f:
        f.write('{"valid": "json"}\n')
        f.write("{invalid json}\n")

    with pytest.raises(DataSourceError) as exc_info:
        load_jsonl_data(str(invalid_jsonl))

    assert "Invalid JSON" in str(exc_info.value)
    assert "line 2" in str(exc_info.value)


def test_load_jsonl_data_empty_lines(tmp_path):
    """Test JSONL file with empty lines (should be skipped)."""
    jsonl_file = tmp_path / "with_empty_lines.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        f.write('{"id": "MSG001", "amount": "100"}\n')
        f.write("\n")  # Empty line
        f.write('{"id": "MSG002", "amount": "200"}\n')
        f.write("   \n")  # Whitespace-only line

    payment_data = load_jsonl_data(str(jsonl_file))

    assert len(payment_data) == 2
    assert payment_data[0]["id"] == "MSG001"
    assert payment_data[1]["id"] == "MSG002"


def test_load_jsonl_data_non_dict(tmp_path):
    """Test DataSourceError for JSONL containing non-dict."""
    invalid_jsonl = tmp_path / "non_dict.jsonl"
    with open(invalid_jsonl, "w", encoding="utf-8") as f:
        f.write('{"valid": "dict"}\n')
        f.write('["not", "a", "dict"]\n')

    with pytest.raises(DataSourceError) as exc_info:
        load_jsonl_data(str(invalid_jsonl))

    assert "Expected JSON object" in str(exc_info.value)
    assert "line 2" in str(exc_info.value).lower()


# =============================================================================
# load_jsonl_data_streaming Tests
# =============================================================================


def test_load_jsonl_data_streaming_chunks(jsonl_file):
    """Test streaming JSONL data in chunks."""
    chunks = list(load_jsonl_data_streaming(jsonl_file, chunk_size=1))

    assert len(chunks) == 2
    assert all(isinstance(chunk, list) for chunk in chunks)
    assert chunks[0][0]["id"] == "MSG001"
    assert chunks[1][0]["id"] == "MSG002"


def test_load_jsonl_data_streaming_large_dataset(large_jsonl_file):
    """Test streaming large JSONL file (5000 records)."""
    chunks = list(load_jsonl_data_streaming(large_jsonl_file, chunk_size=1000))

    assert len(chunks) == 5  # 5000 records / 1000 chunk_size
    assert all(len(chunk) == 1000 for chunk in chunks)

    # Verify first and last records
    assert chunks[0][0]["id"] == "MSG00000"
    assert chunks[-1][-1]["id"] == "MSG04999"


def test_load_jsonl_data_streaming_default_chunk_size(jsonl_file):
    """Test streaming with default chunk_size (1000)."""
    chunks = list(load_jsonl_data_streaming(jsonl_file))

    assert len(chunks) == 1  # 2 records, chunk_size=1000
    assert len(chunks[0]) == 2


def test_load_jsonl_data_streaming_file_not_found():
    """Test FileNotFoundError in JSONL streaming mode."""
    with pytest.raises(FileNotFoundError):
        list(load_jsonl_data_streaming("/nonexistent/file.jsonl"))


def test_load_jsonl_data_streaming_invalid_line(tmp_path):
    """Test DataSourceError for malformed line in streaming mode."""
    invalid_jsonl = tmp_path / "invalid_streaming.jsonl"
    with open(invalid_jsonl, "w", encoding="utf-8") as f:
        f.write('{"id": "MSG001"}\n')
        f.write("{invalid}\n")

    generator = load_jsonl_data_streaming(str(invalid_jsonl), chunk_size=1)
    next(generator)  # First chunk should work

    with pytest.raises(DataSourceError) as exc_info:
        next(generator)  # Second chunk should fail

    assert "Invalid JSON" in str(exc_info.value)


def test_load_jsonl_data_streaming_partial_last_chunk(tmp_path):
    """Test streaming with partial last chunk."""
    jsonl_file = tmp_path / "partial.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for i in range(25):  # 25 records
            f.write(json.dumps({"id": f"MSG{i:03d}"}) + "\n")

    chunks = list(load_jsonl_data_streaming(str(jsonl_file), chunk_size=10))

    assert len(chunks) == 3  # 10, 10, 5
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5  # Partial last chunk


# =============================================================================
# Integration Tests (JSON vs JSONL comparison)
# =============================================================================


def test_json_vs_jsonl_equivalence(payment_input_data, tmp_path):
    """Test that JSON and JSONL produce equivalent results."""
    json_file = tmp_path / "data.json"
    jsonl_file = tmp_path / "data.jsonl"

    # Write JSON (array format)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(payment_input_data, f)

    # Write JSONL
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for record in payment_input_data:
            f.write(json.dumps(record) + "\n")

    json_data = load_json_data(str(json_file))
    jsonl_data = load_jsonl_data(str(jsonl_file))

    assert json_data == jsonl_data


def test_streaming_equivalence(payment_input_data, tmp_path):
    """Test that streaming and non-streaming produce same results."""
    jsonl_file = tmp_path / "streaming_test.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for record in payment_input_data:
            f.write(json.dumps(record) + "\n")

    # Non-streaming
    data_full = load_jsonl_data(str(jsonl_file))

    # Streaming (collect all chunks)
    data_streamed = []
    for chunk in load_jsonl_data_streaming(str(jsonl_file), chunk_size=1):
        data_streamed.extend(chunk)

    assert data_full == data_streamed


# =============================================================================
# Edge Cases
# =============================================================================


def test_load_json_data_unicode_characters(tmp_path):
    """Test JSON with Unicode characters."""
    unicode_data = [
        {
            "id": "MSG001",
            "creditor_name": "Société Générale",
            "amount": "1000.00",
            "note": "Paiement reçu 中文",
        }
    ]

    json_file = tmp_path / "unicode.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(unicode_data, f, ensure_ascii=False)

    payment_data = load_json_data(str(json_file))

    assert payment_data[0]["creditor_name"] == "Société Générale"
    assert "中文" in payment_data[0]["note"]


def test_load_jsonl_data_large_values(tmp_path):
    """Test JSONL with large string values."""
    large_note = "X" * 10000  # 10KB string
    record = {"id": "MSG001", "amount": "100", "note": large_note}

    jsonl_file = tmp_path / "large_values.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    payment_data = load_jsonl_data(str(jsonl_file))

    assert len(payment_data[0]["note"]) == 10000


def test_load_json_data_nested_objects(tmp_path):
    """Test JSON with nested objects (flattened or preserved)."""
    nested_data = [
        {
            "id": "MSG001",
            "amount": "100",
            "metadata": {"created_by": "admin", "priority": "high"},
        }
    ]

    json_file = tmp_path / "nested.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(nested_data, f)

    payment_data = load_json_data(str(json_file))

    assert isinstance(payment_data[0]["metadata"], dict)
    assert payment_data[0]["metadata"]["priority"] == "high"


def test_jsonl_streaming_memory_efficiency(large_jsonl_file):
    """Test that JSONL streaming doesn't load entire file into memory."""
    # This test verifies streaming behavior by checking chunk-by-chunk processing
    chunk_count = 0
    record_count = 0

    for chunk in load_jsonl_data_streaming(large_jsonl_file, chunk_size=500):
        chunk_count += 1
        record_count += len(chunk)
        # Process only first 2 chunks, then break (streaming should allow early exit)
        if chunk_count == 2:
            break

    assert chunk_count == 2
    assert record_count == 1000  # 2 chunks × 500 records


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
