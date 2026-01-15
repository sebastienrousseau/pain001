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

import uuid
from pathlib import Path
from unittest import mock

import pytest
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

    def test_status_completed_job(self):
        """Test status of completed job."""
        job_id = job_manager.create_job()
        job_manager.update_status(
            job_id,
            JobStatus.SUCCESS,
            progress=100,
            result={
                "success": True,
                "message": "✓ XML generated successfully",
                "file_path": "/tmp/test.xml",
            },
        )

        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["result"] is not None
        assert data["result"]["file_path"] == "/tmp/test.xml"


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
