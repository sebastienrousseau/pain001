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
Comprehensive tests for Parquet data loader.

Tests load_parquet_data and load_parquet_data_streaming functions,
including optional pyarrow dependency handling.
"""

from pathlib import Path

import pytest

from pain001.exceptions import DataSourceError

# Import after mocking to test dependency handling
from pain001.parquet.load_parquet_data import (
    HAS_PARQUET_SUPPORT,
    load_parquet_data,
    load_parquet_data_streaming,
)

# Skip all tests if pyarrow not installed
pytestmark = pytest.mark.skipif(
    not HAS_PARQUET_SUPPORT,
    reason="pyarrow not installed - install with: pip install pyarrow",
)


@pytest.fixture
def sample_payment_data():
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


@pytest.fixture
def parquet_file(sample_payment_data, tmp_path):
    """Create a temporary Parquet file."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")
    # noqa: F811
    parquet_file = tmp_path / "payments.parquet"

    # Convert to PyArrow Table and write
    table = pa.Table.from_pylist(sample_payment_data)
    pq.write_table(table, str(parquet_file))

    return str(parquet_file)


@pytest.fixture
def large_parquet_file(tmp_path):
    """Create a large Parquet file for streaming tests (10,000 records)."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")
    # noqa: F811
    parquet_file = tmp_path / "large_payments.parquet"

    # Generate large dataset
    data = []
    for i in range(10000):
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
        data.append(record)

    table = pa.Table.from_pylist(data)
    pq.write_table(table, str(parquet_file))

    return str(parquet_file)


# =============================================================================
# load_parquet_data Tests
# =============================================================================


# noqa: F811
# noqa: F811
def test_load_parquet_data_basic(parquet_file, sample_payment_data):
    """Test loading Parquet file."""
    data = load_parquet_data(parquet_file)

    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == "MSG001"
    assert data[0]["amount"] == "1000.00"
    assert data[1]["id"] == "MSG002"


def test_load_parquet_data_file_not_found():
    """Test FileNotFoundError for nonexistent Parquet file."""
    missing = (
        Path("pain001/test_fixtures") / "nonexistent_parquet_test.parquet"
    )
    with pytest.raises(FileNotFoundError) as exc_info:
        load_parquet_data(str(missing))

    assert "not found" in str(exc_info.value).lower()


def test_load_parquet_data_invalid_file(tmp_path):
    """Test DataSourceError for invalid Parquet file."""
    invalid_file = tmp_path / "invalid.parquet"
    invalid_file.write_text("not a parquet file")

    with pytest.raises(DataSourceError) as exc_info:
        load_parquet_data(str(invalid_file))

    assert "Error reading Parquet file" in str(exc_info.value)


def test_load_parquet_data_empty_file(tmp_path):
    """Test loading empty Parquet file."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    empty_file = tmp_path / "empty.parquet"
    empty_table = pa.Table.from_pylist([])
    pq.write_table(empty_table, str(empty_file))

    with pytest.raises(DataSourceError) as exc_info:
        load_parquet_data(str(empty_file))

    assert (
        "empty" in str(exc_info.value).lower()
        or "no data" in str(exc_info.value).lower()
    )


def test_load_parquet_data_column_types(tmp_path):
    """Test Parquet file with various column types."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")  # noqa: F811
    # noqa: F811
    parquet_file = tmp_path / "types.parquet"
    data = [
        {
            "id": "MSG001",
            "amount": "1000.00",
            "count": 5,
            "is_active": True,
            "rate": 1.25,
        }
    ]

    table = pa.Table.from_pylist(data)
    pq.write_table(table, str(parquet_file))

    result = load_parquet_data(str(parquet_file))

    assert result[0]["id"] == "MSG001"
    assert result[0]["count"] == 5
    assert result[0]["is_active"] is True
    assert result[0]["rate"] == 1.25


# =============================================================================
# load_parquet_data_streaming Tests
# =============================================================================


def test_load_parquet_data_streaming_chunks(parquet_file):
    """Test streaming Parquet data in chunks."""
    chunks = list(load_parquet_data_streaming(parquet_file, chunk_size=1))

    assert len(chunks) == 2
    assert all(isinstance(chunk, list) for chunk in chunks)
    assert chunks[0][0]["id"] == "MSG001"
    assert chunks[1][0]["id"] == "MSG002"


# noqa: F811


# noqa: F811
def test_load_parquet_data_streaming_large_chunk(parquet_file):
    """Test streaming with chunk_size larger than data."""
    chunks = list(load_parquet_data_streaming(parquet_file, chunk_size=10))

    assert len(chunks) == 1
    assert len(chunks[0]) == 2  # noqa: F811


# noqa: F811
def test_load_parquet_data_streaming_default_chunk_size(parquet_file):
    """Test streaming with default chunk_size (1000)."""
    chunks = list(load_parquet_data_streaming(parquet_file))

    assert len(chunks) == 1  # noqa: F811
    assert len(chunks[0]) == 2


# noqa: F811
def test_load_parquet_data_streaming_large_dataset(large_parquet_file):
    """Test streaming large Parquet file (10,000 records)."""
    chunks = list(
        load_parquet_data_streaming(large_parquet_file, chunk_size=2500)
    )

    assert len(chunks) == 4  # 10000 / 2500
    assert all(len(chunk) == 2500 for chunk in chunks)

    # Verify first and last records
    assert chunks[0][0]["id"] == "MSG00000"
    assert chunks[-1][-1]["id"] == "MSG09999"


def test_load_parquet_data_streaming_partial_last_chunk(tmp_path):
    """Test streaming with partial last chunk."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    parquet_file = tmp_path / "partial.parquet"
    data = [{"id": f"MSG{i:03d}", "amount": "100"} for i in range(25)]

    table = pa.Table.from_pylist(data)
    pq.write_table(table, str(parquet_file))

    chunks = list(
        load_parquet_data_streaming(str(parquet_file), chunk_size=10)
    )

    assert len(chunks) == 3  # 10, 10, 5
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5  # Partial last chunk


def test_load_parquet_data_streaming_file_not_found():
    """Test FileNotFoundError in streaming mode."""
    with pytest.raises(FileNotFoundError):
        list(
            load_parquet_data_streaming(
                "pain001/test_fixtures/nonexistent_streaming.parquet"
            )
        )


def test_load_parquet_data_streaming_invalid_file(tmp_path):
    """Test DataSourceError for invalid Parquet in streaming mode."""
    invalid_file = tmp_path / "invalid_streaming.parquet"
    invalid_file.write_text("not parquet")

    with pytest.raises(DataSourceError) as exc_info:
        list(load_parquet_data_streaming(str(invalid_file)))

    assert "Error reading Parquet file" in str(exc_info.value)


# =============================================================================
# Streaming vs Non-Streaming Equivalence
# =============================================================================


def test_streaming_vs_non_streaming_equivalence(parquet_file):
    """Test that streaming and non-streaming produce same results."""
    # Non-streaming
    data_full = load_parquet_data(parquet_file)

    # Streaming (collect all chunks)
    data_streamed = []
    for chunk in load_parquet_data_streaming(parquet_file, chunk_size=1):
        data_streamed.extend(chunk)

    assert data_full == data_streamed


def test_streaming_memory_efficiency(large_parquet_file):
    """Test that streaming doesn't load entire file into memory."""
    # Process only first 2 chunks and exit early (streaming should allow this)
    chunk_count = 0
    record_count = 0

    for chunk in load_parquet_data_streaming(
        large_parquet_file, chunk_size=1000
    ):
        chunk_count += 1
        record_count += len(chunk)
        if chunk_count == 2:
            break

    assert chunk_count == 2
    assert record_count == 2000  # 2 chunks × 1000 records


# =============================================================================
# Edge Cases
# =============================================================================


def test_load_parquet_data_unicode_strings(tmp_path):
    """Test Parquet file with Unicode strings."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    unicode_data = [
        {
            "id": "MSG001",
            "creditor_name": "Société Générale",
            "note": "Paiement reçu 中文",
        }
    ]

    parquet_file = tmp_path / "unicode.parquet"
    table = pa.Table.from_pylist(unicode_data)
    pq.write_table(table, str(parquet_file))

    data = load_parquet_data(str(parquet_file))

    assert data[0]["creditor_name"] == "Société Générale"
    assert "中文" in data[0]["note"]


def test_load_parquet_data_null_values(tmp_path):
    """Test Parquet file with null values."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    data_with_nulls = [
        {"id": "MSG001", "amount": "100", "note": None},
        {"id": "MSG002", "amount": "200", "note": "Valid note"},
    ]

    parquet_file = tmp_path / "nulls.parquet"
    table = pa.Table.from_pylist(data_with_nulls)
    pq.write_table(table, str(parquet_file))

    data = load_parquet_data(str(parquet_file))

    assert data[0]["note"] is None
    assert data[1]["note"] == "Valid note"


def test_load_parquet_data_compression(tmp_path):
    """Test Parquet file with compression (snappy, gzip)."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    data = [{"id": f"MSG{i:03d}", "amount": "100"} for i in range(100)]

    # Test with snappy compression
    snappy_file = tmp_path / "snappy.parquet"
    table = pa.Table.from_pylist(data)
    pq.write_table(table, str(snappy_file), compression="snappy")

    snappy_data = load_parquet_data(str(snappy_file))
    assert len(snappy_data) == 100

    # Test with gzip compression
    gzip_file = tmp_path / "gzip.parquet"
    pq.write_table(table, str(gzip_file), compression="gzip")

    gzip_data = load_parquet_data(str(gzip_file))
    assert len(gzip_data) == 100
    assert snappy_data == gzip_data


# =============================================================================
# Dependency Handling Tests (pyarrow not installed)
# =============================================================================


def test_parquet_support_flag():
    """Test HAS_PARQUET_SUPPORT flag is set correctly."""
    # This will be True if pyarrow is installed, False otherwise
    assert isinstance(HAS_PARQUET_SUPPORT, bool)


@pytest.mark.skipif(
    HAS_PARQUET_SUPPORT, reason="Test requires pyarrow NOT installed"
)
def test_load_parquet_data_without_pyarrow():
    """Test DataSourceError when pyarrow not installed."""
    with pytest.raises(DataSourceError) as exc_info:
        load_parquet_data("dummy.parquet")

    error_msg = str(exc_info.value)
    assert "pyarrow" in error_msg.lower()
    assert "pip install pyarrow" in error_msg


@pytest.mark.skipif(
    HAS_PARQUET_SUPPORT, reason="Test requires pyarrow NOT installed"
)
def test_load_parquet_data_streaming_without_pyarrow():
    """Test DataSourceError when pyarrow not installed (streaming)."""
    with pytest.raises(DataSourceError) as exc_info:
        list(load_parquet_data_streaming("dummy.parquet"))

    error_msg = str(exc_info.value)
    assert "pyarrow" in error_msg.lower()


# =============================================================================
# Integration Tests
# =============================================================================


def test_parquet_roundtrip(sample_payment_data, tmp_path):
    """Test writing and reading back Parquet file."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    parquet_file = tmp_path / "roundtrip.parquet"

    # Write
    table = pa.Table.from_pylist(sample_payment_data)
    pq.write_table(table, str(parquet_file))

    # Read
    data = load_parquet_data(str(parquet_file))

    # Compare (note: types may differ slightly)
    assert len(data) == len(sample_payment_data)
    assert data[0]["id"] == sample_payment_data[0]["id"]
    assert data[1]["creditor_name"] == sample_payment_data[1]["creditor_name"]


def test_parquet_vs_json_equivalence(sample_payment_data, tmp_path):
    """Test that Parquet and JSON produce equivalent results."""
    pa = None  # Initialize to satisfy CodeQL
    pq = None
    try:
        import pyarrow as pa  # type: ignore[import-untyped,no-redef]
        import pyarrow.parquet as pq  # type: ignore[import-untyped,no-redef]
    except ImportError:
        pytest.skip("pyarrow not available")

    import json

    # Write Parquet
    parquet_file = tmp_path / "data.parquet"
    table = pa.Table.from_pylist(sample_payment_data)
    pq.write_table(table, str(parquet_file))

    # Write JSON
    json_file = tmp_path / "data.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(sample_payment_data, f)

    # Load both
    parquet_data = load_parquet_data(str(parquet_file))

    from pain001.json.load_json_data import load_json_data

    json_data = load_json_data(str(json_file))

    # Compare
    assert len(parquet_data) == len(json_data)
    assert parquet_data[0]["id"] == json_data[0]["id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
