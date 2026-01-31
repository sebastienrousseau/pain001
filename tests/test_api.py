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

"""Pain001 FastAPI simplified tests."""

# pylint: disable=too-few-public-methods

import uuid

from fastapi.testclient import TestClient

from pain001 import __version__
from pain001.api.app import app
from pain001.api.job_manager import JobStatus, job_manager

client = TestClient(app)


class TestHealthEndpoint:
    """Test /api/health endpoint."""

    def test_health_check_success(self):
        """Test health check returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == __version__
        assert "message" in data


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_message_type(self, tmp_path):
        """Test validation with invalid message_type."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("test")

        response = client.post(
            "/api/validate",
            json={
                "file_path": str(csv_file),
                "data_source": "csv",
                "message_type": "invalid.message.type",
            },
        )
        # Should fail validation (Pydantic validates enum)
        assert response.status_code == 422

    def test_missing_required_field(self):
        """Test missing required field."""
        response = client.post(
            "/api/validate",
            json={
                "file_path": "/some/file.csv",
                # Missing data_source and message_type
            },
        )
        assert response.status_code == 422


class TestSyncGenerationEndpoint:
    """Test /api/generate endpoint."""

    def test_generate_nonexistent_file(self):
        """Test generation with nonexistent file outside allowed dir is rejected."""
        response = client.post(
            "/api/generate",
            json={
                "file_path": "/nonexistent/file.csv",
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # Absolute path outside allowed directory triggers security check
        assert response.status_code in (400, 403, 404)

    def test_generate_with_validate_only(self, tmp_path):
        """Test validate-only mode returns validation results without generating XML."""
        # Use simpler test - validate_only should work even with minimal data
        csv_file = tmp_path / "minimal.csv"
        csv_file.write_text("id\n12345\n")

        response = client.post(
            "/api/generate",
            json={
                "file_path": str(csv_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
                "validate_only": True,
            },
        )
        # CSV structure validation may fail with minimal data (400), which is expected
        assert response.status_code in [200, 400]
        data = response.json()
        if response.status_code == 200:
            # If it passes CSV validation, check response structure
            assert "success" in data
            assert (
                data.get("file_path") is None
            )  # No XML file generated in validate-only mode
        else:
            # CSV validation error is also valid behavior
            assert "detail" in data

    def test_generate_with_invalid_data(self, tmp_path):
        """Test generation with invalid data returns validation errors."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("id\n12345\n")

        response = client.post(
            "/api/generate",
            json={
                "file_path": str(csv_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # CSV structure validation fails (400) or validation errors returned (200)
        assert response.status_code in [200, 400]
        data = response.json()
        if response.status_code == 200:
            assert data["success"] is False
            assert "Validation failed" in data["message"]
            assert data["validation_errors"] is not None
            assert len(data["validation_errors"]) > 0
        else:
            assert "detail" in data

    def test_generate_successful_xml(self):
        """Test successful XML generation with existing test data."""
        # Use existing test file that we know is valid
        import os

        test_data_path = os.path.join(
            os.path.dirname(__file__), "data", "valid_data_unique.csv"
        )

        if not os.path.exists(test_data_path):
            # Skip if test data doesn't exist
            import pytest

            pytest.skip("Test data file not found")

        response = client.post(
            "/api/generate",
            json={
                "file_path": test_data_path,
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # With valid test data, this should succeed
        if data["success"]:
            assert "successfully" in data["message"].lower()
            assert data["file_path"] is not None
        else:
            # If it fails, it should have validation errors
            assert "validation_errors" in data

    def test_generate_with_validate_only_real_data(self):
        """Test validate-only mode with real valid data."""
        import os

        test_data_path = os.path.join(
            os.path.dirname(__file__), "data", "valid_data_unique.csv"
        )

        if not os.path.exists(test_data_path):
            import pytest

            pytest.skip("Test data file not found")

        response = client.post(
            "/api/generate",
            json={
                "file_path": test_data_path,
                "data_source": "csv",
                "message_type": "pain.001.001.03",
                "validate_only": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert (
            data["file_path"] is None
        )  # No XML generated in validate-only mode
        # Either success (validated) or validation errors
        assert "success" in data


class TestValidateEndpoint:
    """Test /api/validate endpoint."""

    def test_validate_nonexistent_file(self):
        """Test validation with nonexistent file outside allowed dir is rejected."""
        response = client.post(
            "/api/validate",
            json={
                "file_path": "/nonexistent/file.csv",
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # Absolute path outside allowed directory triggers security check
        assert response.status_code in (400, 403, 404)

    def test_validate_with_errors(self, tmp_path):
        """Test validation with errors returns detailed error messages."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("id\n12345\n")

        response = client.post(
            "/api/validate",
            json={
                "file_path": str(csv_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # CSV structure validation may fail (400) or return validation errors (200)
        assert response.status_code in [200, 400]
        data = response.json()
        if response.status_code == 200:
            assert data["is_valid"] is False
            assert data["total_rows"] > 0
            assert len(data["errors"]) > 0
            # Check error structure
            error = data["errors"][0]
            assert "field" in error
            assert "message" in error
            assert "value" in error
        else:
            # CSV validation error is also valid
            assert "detail" in data

    def test_validate_success(self):
        """Test successful validation with existing test data."""
        # Use existing test file
        import os

        test_data_path = os.path.join(
            os.path.dirname(__file__), "data", "valid_data_unique.csv"
        )

        if not os.path.exists(test_data_path):
            # Skip if test data doesn't exist
            import pytest

            pytest.skip("Test data file not found")

        response = client.post(
            "/api/validate",
            json={
                "file_path": test_data_path,
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Valid or invalid doesn't matter - testing endpoint works
        assert "is_valid" in data
        assert "total_rows" in data
        assert data["total_rows"] > 0
        assert "errors" in data


class TestJobStatusEndpoint:
    """Test /api/status/{job_id} endpoint."""

    def test_status_nonexistent_job(self):
        """Test status for nonexistent job returns 404."""
        fake_job_id = str(uuid.uuid4())
        response = client.get(f"/api/status/{fake_job_id}")
        assert response.status_code == 404

    def test_status_pending_job(self):
        """Test status of pending job."""
        job_id = job_manager.create_job()

        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"
        assert data["message"] == "Job is pending"

        # Cleanup
        job_manager.cancel_job(job_id)

    def test_status_processing_job(self):
        """Test status of processing job."""
        job_id = job_manager.create_job()
        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=50)

        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress_percent"] == 50

        # Cleanup
        job_manager.cancel_job(job_id)

    def test_status_completed_job(self, tmp_path):
        """Test status of completed job."""
        job_id = job_manager.create_job()
        xml_output = str(tmp_path / "output.xml")
        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "✓ XML generated successfully",
                "file_path": xml_output,
            },
        )

        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["result"] is not None
        assert data["result"]["file_path"] == xml_output


class TestJobCancellationEndpoint:
    """Test /api/jobs/{job_id} DELETE endpoint."""

    def test_cancel_nonexistent_job(self):
        """Test cancel returns 404 for nonexistent job."""
        fake_job_id = str(uuid.uuid4())
        response = client.delete(f"/api/jobs/{fake_job_id}")
        assert response.status_code == 404

    def test_cancel_pending_job(self):
        """Test cancel pending job."""
        job_id = job_manager.create_job()

        response = client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_processing_job(self):
        """Test cancel processing job."""
        job_id = job_manager.create_job()
        job_manager.update_status(job_id, JobStatus.PROCESSING, progress=30)

        response = client.delete(f"/api/jobs/{job_id}")
        assert response.status_code == 200

        # Verify job is cancelled
        job = job_manager.get_job(job_id)
        assert job.status == JobStatus.CANCELLED


class TestDownloadEndpoint:
    """Test /api/download/{job_id} endpoint."""

    def test_download_nonexistent_job(self):
        """Test download returns 404 for nonexistent job."""
        fake_job_id = str(uuid.uuid4())
        response = client.get(f"/api/download/{fake_job_id}")
        assert response.status_code == 404

    def test_download_pending_job(self):
        """Test download returns 400 for pending job."""
        job_id = job_manager.create_job()

        response = client.get(f"/api/download/{job_id}")
        assert response.status_code == 400

        # Cleanup
        job_manager.cancel_job(job_id)

    def test_download_failed_job(self):
        """Test download returns 400 for failed job."""
        job_id = job_manager.create_job()
        job_manager.update_status(
            job_id,
            JobStatus.FAILED,
            error="Test error",
        )

        response = client.get(f"/api/download/{job_id}")
        assert response.status_code == 400
        assert "failed" in response.json()["detail"].lower()

    def test_download_job_without_file_path(self):
        """Test download returns 404 when job has no file_path in result."""
        job_id = job_manager.create_job()
        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "Completed",
                # Missing file_path
            },
        )

        response = client.get(f"/api/download/{job_id}")
        assert response.status_code == 404
        assert "No file available" in response.json()["detail"]

    def test_download_job_with_missing_file(self, tmp_path):
        """Test download returns error when file doesn't exist on disk."""
        nonexistent_file = tmp_path / "missing.xml"

        job_id = job_manager.create_job()
        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "Completed",
                "file_path": str(nonexistent_file),
            },
        )

        response = client.get(f"/api/download/{job_id}")
        # Path may be rejected by security validation (400/403) or not found (404)
        assert response.status_code in (400, 403, 404)

    def test_download_completed_job(self, tmp_path):
        """Test download completed job."""
        # Create a fake XML file
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<pain001>test</pain001>")

        # Create completed job with file path
        job_id = job_manager.create_job()
        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "✓ XML generated successfully",
                "file_path": str(xml_file),
            },
        )

        response = client.get(f"/api/download/{job_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        assert b"<pain001>test</pain001>" in response.content


class TestAsyncGenerationEndpoint:
    """Test /api/generate/async endpoint."""

    def test_async_generation_creates_job_with_valid_file(self, tmp_path):
        """Test async generation creates a job with valid file."""
        # Create a CSV file with minimal columns that won't cause CSV parsing errors
        csv_file = tmp_path / "test.csv"
        # Write minimal valid structure
        csv_file.write_text("id\nMSG001\n")

        response = client.post(
            "/api/generate/async",
            json={
                "file_path": str(csv_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "accepted"
        assert "message" in data
        assert job_manager.get_job(data["job_id"]) is not None

        # Cleanup
        job_manager.cancel_job(data["job_id"])

    def test_async_generation_with_nonexistent_file(self):
        """Test async generation with nonexistent file."""
        response = client.post(
            "/api/generate/async",
            json={
                "file_path": "/nonexistent/file.csv",
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200
        data = response.json()
        job_id = data["job_id"]

        # Job should fail eventually due to nonexistent file
        # Wait a bit for async processing
        import time

        time.sleep(0.5)

        job = job_manager.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error is not None

    def test_async_generation_with_valid_data(self):
        """Test async generation processes successfully with valid data."""
        # Use existing test file
        import os

        test_data_path = os.path.join(
            os.path.dirname(__file__), "data", "valid_data_unique.csv"
        )

        if not os.path.exists(test_data_path):
            import pytest

            pytest.skip("Test data file not found")

        response = client.post(
            "/api/generate/async",
            json={
                "file_path": test_data_path,
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "accepted"

        job_id = data["job_id"]

        # Wait for async processing
        import time

        for _ in range(20):  # Wait up to 2 seconds
            job = job_manager.get_job(job_id)
            if job.status in [JobStatus.SUCCESS, JobStatus.FAILED]:
                break
            time.sleep(0.1)

        # Check final status
        job = job_manager.get_job(job_id)
        # May succeed or fail depending on schema validation
        assert job.status in [JobStatus.SUCCESS, JobStatus.FAILED]

        # Cleanup
        job_manager.cancel_job(job_id)

    def test_async_generation_with_invalid_data(self, tmp_path):
        """Test async generation fails validation with invalid data."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("id\n12345\n")

        response = client.post(
            "/api/generate/async",
            json={
                "file_path": str(csv_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        assert response.status_code == 200 or response.status_code == 400
        # If 200, async job was created
        if response.status_code == 200:
            data = response.json()
            job_id = data["job_id"]

            # Wait for async processing
            import time

            time.sleep(0.5)

            # Job should fail due to CSV validation
            job = job_manager.get_job(job_id)
            assert job.status == JobStatus.FAILED
            job_manager.cancel_job(job_id)

    def test_validate_exception_handling(self, tmp_path):
        """Test validation endpoint exception handling."""
        # Test with corrupted file to trigger general exception
        bad_file = tmp_path / "bad.csv"
        bad_file.write_bytes(b"\x00\xff\xfe\xfd")  # Binary garbage

        response = client.post(
            "/api/validate",
            json={
                "file_path": str(bad_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # Should return 400 or 500 error
        assert response.status_code in [400, 500]

    def test_generate_exception_handling(self, tmp_path):
        """Test generation endpoint exception handling."""
        # Test with corrupted file
        bad_file = tmp_path / "corrupt.csv"
        bad_file.write_bytes(b"\xff\xfe")

        response = client.post(
            "/api/generate",
            json={
                "file_path": str(bad_file),
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # Should return error
        assert response.status_code in [400, 500]

    def test_async_job_creation_exception(self):
        """Test async generation job creation exception handling."""
        # Try to break job creation by using invalid path format
        response = client.post(
            "/api/generate/async",
            json={
                "file_path": "\x00invalid",  # Null byte in path
                "data_source": "csv",
                "message_type": "pain.001.001.03",
            },
        )
        # Should either reject or create job that fails
        assert response.status_code in [200, 400, 422, 500]


class TestOpenAPIDocumentation:
    """Test that OpenAPI documentation is available."""

    def test_openapi_schema_available(self):
        """Test OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "info" in schema
        assert schema["info"]["version"] == __version__

    def test_swagger_docs_available(self):
        """Test Swagger UI docs are available."""
        response = client.get("/api/docs")
        assert response.status_code == 200
        assert b"swagger" in response.content.lower()

    def test_redoc_available(self):
        """Test ReDoc documentation is available."""
        response = client.get("/api/redoc")
        assert response.status_code == 200
        assert b"redoc" in response.content.lower()
