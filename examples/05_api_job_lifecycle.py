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

"""Walk the REST API job lifecycle: submit, poll, download, cancel.

Uses FastAPI's in-process test client against the same ``app`` object
that ``uvicorn pain001.api.app:app`` serves, so every request below
maps 1:1 to an HTTP call against a running server. Requires the API
extra (``pip install pain001[api]``).

The API only reads data files below the server's working directory,
so run this from the repository root::

    python examples/05_api_job_lifecycle.py
"""

import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from pain001.api.app import app

# JSON rather than CSV: the API validates rows against a typed JSON
# schema, and JSON carries the native integer/boolean types it expects.
DATA_FILE = "examples/data/payments.json"
MESSAGE_TYPE = "pain.001.001.09"


def wait_for_job(
    client: TestClient, job_id: str, timeout: float = 30.0
) -> dict[str, object]:
    """Poll ``/api/v1/status/{job_id}`` until the job reaches a final state.

    Args:
        client: API test client.
        job_id: Identifier returned by ``/api/v1/generate/async``.
        timeout: Maximum seconds to wait.

    Returns:
        The final job status payload.

    Raises:
        TimeoutError: If the job does not finish within ``timeout``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status: dict[str, object] = client.get(
            f"/api/v1/status/{job_id}"
        ).json()
        if status["status"] in {"success", "failed", "cancelled"}:
            return status
        time.sleep(0.2)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


def run(client: TestClient) -> None:
    """Run health check, sync validation, and the async job lifecycle.

    Args:
        client: API test client with a running event loop.
    """
    health = client.get("/api/v1/health").json()
    print(
        f"GET  /api/v1/health          -> {health['status']} v{health['version']}"
    )

    response = client.post(
        "/api/v1/generate",
        json={
            "data_source": "json",
            "file_path": DATA_FILE,
            "message_type": MESSAGE_TYPE,
            "validate_only": True,
        },
    )
    assert response.status_code == 200, response.text
    print(f"POST /api/v1/generate        -> {response.json()['message']}")

    # The download endpoint only serves files below the server's working
    # directory, so the output directory must live under it too.
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as output_dir:
        response = client.post(
            "/api/v1/generate/async",
            json={
                "data_source": "json",
                "file_path": DATA_FILE,
                "message_type": MESSAGE_TYPE,
                "output_dir": output_dir,
            },
        )
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]
        print(f"POST /api/v1/generate/async  -> job {job_id}")

        status = wait_for_job(client, job_id)
        assert status["status"] == "success", status
        print(f"GET  /api/v1/status/{{id}}     -> {status['status']}")

        download = client.get(f"/api/v1/download/{job_id}")
        assert download.status_code == 200, download.text
        print(
            f"GET  /api/v1/download/{{id}}   -> {len(download.content)} bytes of XML"
        )

    response = client.post(
        "/api/v1/generate/async",
        json={
            "data_source": "json",
            "file_path": DATA_FILE,
            "message_type": MESSAGE_TYPE,
        },
    )
    second_job = response.json()["job_id"]
    response = client.delete(f"/api/v1/jobs/{second_job}")
    assert response.status_code == 200, response.text
    print(f"DELETE /api/v1/jobs/{{id}}     -> {response.json()['status']}")


def main() -> None:
    """Open the client inside a context manager so the app's event loop
    stays alive between requests, letting background jobs progress."""
    with TestClient(app) as client:
        run(client)


if __name__ == "__main__":
    main()
