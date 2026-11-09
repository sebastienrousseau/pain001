# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Bound public metadata requests and keep credentials out of arguments."""

from __future__ import annotations

import subprocess
from typing import Any

import ecosystem_audit
import pytest


def runner(
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    status: int = 200,
    code: int = 0,
) -> list[tuple[list[str], dict[str, Any]]]:
    """Replace curl with a deterministic subprocess response."""
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args, code, body + f"\n{status}".encode(), b""
        )

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_github_token_is_sent_only_to_github_via_standard_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public PyPI requests and process listings cannot reveal the token."""
    calls = runner(monkeypatch, b'{"ok": true}')
    client = ecosystem_audit.Client(token="synthetic-token")
    assert client.json("https://api.github.com/repos/example/project") == {
        "ok": True
    }
    client.json("https://pypi.org/pypi/pain001/json")
    assert b"synthetic-token" in calls[0][1]["input"]
    assert b"synthetic-token" not in calls[1][1]["input"]
    assert all(
        "synthetic-token" not in argument
        for args, _ in calls
        for argument in args
    )
    assert "--location-trusted" not in calls[0][0]
    assert "--max-filesize" in calls[0][0]
    assert calls[0][1]["timeout"] <= 125


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com/x",
        "file:///etc/passwd",
        "https://example.test/x",
        "https://user@api.github.com/x",
        "https://api.github.com:8443/x",
    ],
)
def test_untrusted_initial_url_is_rejected(url: str) -> None:
    """The inventory cannot redirect a credentialed request to arbitrary hosts."""
    with pytest.raises(ValueError):
        ecosystem_audit.Client(token="synthetic").get(url)


@pytest.mark.parametrize(
    ("code", "status"), [(22, 404), (22, 403), (28, 0), (63, 200)]
)
def test_http_and_connection_failures_are_not_empty_metadata(
    monkeypatch: pytest.MonkeyPatch, code: int, status: int
) -> None:
    """Missing releases, rate limits, timeouts and oversized bodies all fail."""
    runner(monkeypatch, b"", status, code)
    with pytest.raises(ValueError):
        ecosystem_audit.Client().json("https://pypi.org/pypi/pain001/json")


def test_malformed_json_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A proxy error page is not a successful publication response."""
    runner(monkeypatch, b"<html>unavailable</html>")
    with pytest.raises(ValueError):
        ecosystem_audit.Client().json("https://pypi.org/pypi/pain001/json")


def test_repeated_public_metadata_requests_are_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The website and release checks share the same core metadata snapshot."""
    calls = runner(monkeypatch, b"{}")
    client = ecosystem_audit.Client()
    for _ in range(2):
        client.json("https://pypi.org/pypi/pain001/json")
    assert len(calls) == 1


def test_official_mcp_registry_is_read_without_github_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The published server record is public and has its own trusted origin."""
    calls = runner(monkeypatch, b"{}")
    ecosystem_audit.Client(token="synthetic").json(
        "https://registry.modelcontextprotocol.io/v0.1/servers"
    )
    assert b"synthetic" not in calls[0][1]["input"]


@pytest.mark.parametrize(
    "error", [FileNotFoundError("curl"), subprocess.TimeoutExpired("curl", 25)]
)
def test_subprocess_failures_are_reported(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """A missing local prerequisite never becomes an apparent pass."""

    def fail(*args: Any, **kwargs: Any) -> None:
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(ValueError):
        ecosystem_audit.Client().get("https://pypi.org/pypi/pain001/json")


@pytest.mark.parametrize("timeout", [0, 121])
def test_request_timeouts_are_always_bounded(
    monkeypatch: pytest.MonkeyPatch, timeout: int
) -> None:
    """Caller configuration cannot create an unbounded scheduled request."""
    runner(monkeypatch, b"{}")
    with pytest.raises(ValueError, match="timeout"):
        ecosystem_audit.Client(timeout=timeout).get(
            "https://pypi.org/pypi/pain001/json"
        )


@pytest.mark.parametrize(
    "token", ["synthetic\nheader: injection", "synthetic\rheader: injection"]
)
def test_header_values_cannot_inject_curl_configuration(
    monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    """Reject control characters before constructing the config stream."""
    runner(monkeypatch, b"{}")
    with pytest.raises(ValueError, match="header"):
        ecosystem_audit.Client(token=token).get(
            "https://api.github.com/repos/example/project"
        )
