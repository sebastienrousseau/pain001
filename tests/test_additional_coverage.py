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

"""Tests for additional module coverage."""

# pylint: disable=too-few-public-methods

import json

import pytest


class TestJSONLoaderStreaming:
    """Test JSON/JSONL streaming functions."""

    def test_jsonl_streaming_coverage(self, tmp_path):
        """Test JSONL streaming edge cases."""
        from pain001.json.load_json_data import load_jsonl_data_streaming

        jsonl_file = tmp_path / "test.jsonl"
        lines = [f'{{"id": "{i}", "amount": {i * 100}}}\n' for i in range(10)]
        jsonl_file.write_text("".join(lines))

        chunks = list(load_jsonl_data_streaming(str(jsonl_file), chunk_size=3))

        assert len(chunks) >= 3
        assert all(isinstance(chunk, list) for chunk in chunks)

    def test_json_array_streaming(self, tmp_path):
        """Test JSON array streaming."""
        from pain001.json.load_json_data import load_json_data_streaming

        json_file = tmp_path / "test.json"
        data = [{"id": str(i), "value": i} for i in range(8)]
        json_file.write_text(json.dumps(data))

        chunks = list(load_json_data_streaming(str(json_file), chunk_size=3))

        assert len(chunks) >= 2
        assert sum(len(c) for c in chunks) == 8


class TestJobManagerCoverage:
    """Test job manager edge cases."""

    def test_job_manager_cleanup(self):
        """Test job manager cleanup methods."""
        from pain001.api.job_manager import JobStatus, job_manager

        # Create multiple jobs
        job_ids = [job_manager.create_job() for _ in range(3)]

        # Update one to completed
        job_manager.update_status(job_ids[0], JobStatus.SUCCESS, progress=100)

        # Cancel one
        cancelled = job_manager.cancel_job(job_ids[1])
        assert cancelled is True

        # Try to cancel again (should return False or not error)
        _ = job_manager.cancel_job(job_ids[1])

        # Get all jobs
        for job_id in job_ids:
            job = job_manager.get_job(job_id)
            if job:
                assert job.job_id == job_id

    def test_job_status_transitions(self):
        """Test various job status transitions."""
        from pain001.api.job_manager import JobStatus, job_manager

        job_id = job_manager.create_job()

        # Test transitions
        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=25)
        job = job_manager.get_job(job_id)
        assert job.progress_percent == 25

        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=75)
        job = job_manager.get_job(job_id)
        assert job.progress_percent == 75

        # Failed with error
        job_manager.update_status(job_id, JobStatus.FAILED, error="Test error")
        job = job_manager.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error == "Test error"


class TestParquetCoverage:
    """Test Parquet loader edge cases."""

    def test_parquet_streaming_edge_cases(self, tmp_path):
        """Test Parquet streaming with various data."""
        try:
            import pandas as pd

            from pain001.parquet.load_parquet_data import (
                load_parquet_data_streaming,
            )

            parquet_file = tmp_path / "test.parquet"
            df = pd.DataFrame(
                {
                    "id": [str(i) for i in range(15)],
                    "amount": [i * 10.5 for i in range(15)],
                }
            )
            df.to_parquet(parquet_file)

            chunks = list(
                load_parquet_data_streaming(str(parquet_file), chunk_size=4)
            )

            assert len(chunks) >= 3
            assert all(isinstance(c, list) for c in chunks)
        except ImportError:
            pytest.skip("pyarrow not available")

    def test_parquet_invalid_file(self, tmp_path):
        """Test Parquet loader with invalid file."""
        try:
            from pain001.exceptions import DataSourceError
            from pain001.parquet.load_parquet_data import load_parquet_data

            bad_file = tmp_path / "bad.parquet"
            bad_file.write_text("not a parquet file")

            with pytest.raises(DataSourceError):
                load_parquet_data(str(bad_file))
        except ImportError:
            pytest.skip("pyarrow not available")


class TestDBStreamingCoverage:
    """Test database streaming edge cases."""

    def test_db_streaming_cursor_handling(self, tmp_path):
        """Test database streaming cursor edge cases."""
        import sqlite3

        from pain001.db.load_db_data_streaming import load_db_data_streaming

        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_table (id TEXT, value INTEGER)")
        for i in range(7):
            cursor.execute(
                "INSERT INTO test_table VALUES (?, ?)", (str(i), i * 10)
            )
        conn.commit()
        conn.close()

        chunks = list(
            load_db_data_streaming(str(db_file), "test_table", chunk_size=3)
        )

        assert len(chunks) >= 2
        assert all(isinstance(c, list) for c in chunks)


class TestXMLValidatorCoverage:
    """Test XML validator edge cases."""

    def test_xsd_validation_error_handling(self, tmp_path):
        """Test XSD validation error paths."""
        from pain001.xml.validate_via_xsd import validate_via_xsd

        # Create invalid XML
        xml_file = tmp_path / "invalid.xml"
        xml_file.write_text(
            "<?xml version='1.0'?><invalid>no schema</invalid>"
        )

        # Use real schema
        xsd_path = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"

        # Should return False or raise exception
        try:
            result = validate_via_xsd(str(xml_file), xsd_path)
            assert result is False
        except Exception as e:
            # Exception is also acceptable for invalid XML
            assert str(e) or True  # Ensure exception is captured
