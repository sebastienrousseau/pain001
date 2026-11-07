# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Start ``pain001 serve`` for real and call it over HTTP.

Example 05 drives the REST API in-process with a test client; this one
runs the launcher a deployment would run:

* ``pain001 serve --host 127.0.0.1 --port <free port>`` in a
  subprocess, waiting until ``GET /api/v1/health`` answers
* ``PAIN001_API_KEY`` set to a synthetic key, so a request without the
  bearer token is refused with ``401`` and one with it is accepted
* ``POST /api/v1/generate`` validating ``examples/data/payments.json``
* a graceful shutdown on ``SIGTERM`` (what a container stop sends):
  uvicorn finishes the application's shutdown, then exits with the
  signal it was sent

Needs the ``api`` extra (``pip install pain001[api]``); the script says
so and exits ``0`` without it. Run from the repository root::

    python examples/26_rest_server.py
"""

import importlib.util
import json
import os
import signal
import socket
import subprocess  # nosec B404
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
API_KEY = "example-only-key"  # nosec B105 - synthetic loopback credential
REQUEST = {
    "data_source": "json",
    "file_path": "examples/data/payments.json",
    "message_type": "pain.001.001.03",
    "validate_only": True,
}


def free_port() -> int:
    """Return a TCP port on loopback that nothing is listening on."""
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def call(
    url: str, payload: dict[str, object] | None = None, key: str = ""
) -> tuple[int, dict[str, object]]:
    """Send one request and return its status code and JSON body.

    Args:
        url: Full URL on the loopback server.
        payload: JSON body to POST, or None for a GET.
        key: Bearer token to send, or empty to send none.

    Returns:
        The HTTP status code and the decoded JSON response.
    """
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data)  # noqa: S310
    request.add_header("Content-Type", "application/json")
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def wait_until_healthy(base: str, server: subprocess.Popen[str]) -> dict:
    """Poll the health endpoint until the server answers or gives up.

    Args:
        base: Base URL of the API (``http://host:port/api/v1``).
        server: The server process, checked so a crash fails fast.

    Returns:
        The health response body.
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert server.poll() is None, "server exited during start-up"
        try:
            status, body = call(f"{base}/health")
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
            continue
        assert status == 200, body
        return body
    raise TimeoutError("server did not become healthy within 30 seconds")


def exercise(base: str) -> None:
    """Show the API key being enforced, then validate the sample data."""
    status, body = call(f"{base}/generate", REQUEST)
    assert status == 401, (status, body)
    print("POST /generate, no key  -> 401 (PAIN001_API_KEY is set)")

    status, body = call(f"{base}/generate", REQUEST, key=API_KEY)
    assert status == 200, (status, body)
    print(f"POST /generate, bearer  -> 200 ({body['message']})")


def stop(server: subprocess.Popen[str]) -> int:
    """Send SIGTERM, as a container stop would, and wait for the exit."""
    server.terminate()
    try:
        return server.wait(timeout=15)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
        raise


def main() -> None:
    """Start the server, exercise it over HTTP, then shut it down."""
    if importlib.util.find_spec("uvicorn") is None:
        print("REST server -> skipped (needs pip install pain001[api])")
        return
    port = free_port()
    env = dict(os.environ) | {"PAIN001_API_KEY": API_KEY}
    args = [sys.executable, "-m", "pain001", "serve"]
    args += ["--host", HOST, "--port", str(port)]
    base = f"http://{HOST}:{port}/api/v1"
    with tempfile.TemporaryFile("w+", encoding="utf-8") as log:
        server = subprocess.Popen(  # nosec B603
            args, cwd=REPO_ROOT, env=env, stdout=log, stderr=log, text=True
        )
        try:
            health = wait_until_healthy(base, server)
            print(f"pain001 serve on :{port} -> {health['status']}")
            exercise(base)
        finally:
            code = stop(server)
        log.seek(0)
        output = log.read()
    assert "Application shutdown complete" in output, output
    assert code in (0, -signal.SIGTERM), code
    print(f"SIGTERM                 -> graceful shutdown (exit {code})")


if __name__ == "__main__":
    main()
