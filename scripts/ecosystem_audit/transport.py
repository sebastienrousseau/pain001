# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Bounded HTTPS metadata requests without Python runtime dependencies."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Protocol
from urllib.parse import urlsplit

HOSTS = {
    "api.github.com",
    "pypi.org",
    "ghcr.io",
    "pain001.com",
    "registry.modelcontextprotocol.io",
}


class Transport(Protocol):
    """The byte/JSON boundary replaced by synthetic data in tests."""

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """Read an HTTPS resource."""
        ...

    def json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        """Read a JSON resource."""
        ...


class Client:
    """Use curl's TLS, redirect and connection handling on local/CI hosts.

    curl strips Authorization on cross-origin redirects; --location-trusted
    must never be used. Headers go through stdin, not the process arguments.
    """

    def __init__(self, token: str | None = None, timeout: int = 20) -> None:
        self.token = (
            token
            if token is not None
            else os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
        )
        self.timeout = timeout
        self.cache: dict[tuple[str, tuple[tuple[str, str], ...]], bytes] = {}

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """Fetch public metadata, refusing unsafe origins and HTTP failures."""
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in HOSTS
            or parsed.username
            or parsed.port not in (None, 443)
        ):
            raise ValueError("refusing untrusted metadata URL: " + url)
        request_headers = {"Accept": "application/json", **(headers or {})}
        if parsed.hostname == "api.github.com" and self.token:
            request_headers["Authorization"] = "Bearer " + self.token
        key = (url, tuple(sorted(request_headers.items())))
        if key not in self.cache:
            self.cache[key] = self._request(url, request_headers)
        return self.cache[key]

    def _request(self, url: str, headers: dict[str, str]) -> bytes:
        """Run a bounded request and retain neither credentials nor stderr."""
        if not 1 <= self.timeout <= 120:
            raise ValueError("timeout must be between 1 and 120 seconds")
        if any("\n" in value or "\r" in value for value in headers.values()):
            raise ValueError("invalid metadata request header")
        config = "".join(
            "header = " + json.dumps(f"{name}: {value}") + "\n"
            for name, value in headers.items()
        )
        args = [
            "curl",
            "--disable",
            "--silent",
            "--show-error",
            "--fail",
            "--location",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--max-time",
            str(self.timeout),
            "--max-filesize",
            "8388608",
            "--write-out",
            "\n%{http_code}",
            "--config",
            "-",
            url,
        ]
        try:
            result = subprocess.run(
                args,
                input=config.encode(),
                capture_output=True,
                timeout=self.timeout + 5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError(
                f"could not execute curl for {url}: {type(error).__name__}"
            ) from error
        payload, _, status = result.stdout.rpartition(b"\n")
        if result.returncode or status != b"200":
            raise ValueError(
                f"HTTP {status.decode(errors='replace')} / curl {result.returncode}: {url}"
            )
        return payload

    def json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        """Decode metadata; an HTML error page is never an empty success."""
        return json.loads(self.get(url, headers))
