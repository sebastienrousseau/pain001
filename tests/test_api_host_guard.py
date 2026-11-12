# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""A keyless REST API answers only requests addressed to loopback.

Without ``PAIN001_API_KEY`` the API is open, so it answers only
requests whose ``Host`` and ``Origin`` name the local machine.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from pain001.api.app import app  # noqa: E402
from pain001.api.host_guard import (  # noqa: E402
    allowed_host,
    hostname,
)

UNKNOWN_JOB = "/api/v1/status/00000000-0000-4000-8000-000000000000"
LOCAL = "http://127.0.0.1:8000"


@pytest.fixture(autouse=True)
def _keyless(monkeypatch):
    """Run with no key and no extra hosts, as `pain001 serve` does."""
    monkeypatch.delenv("PAIN001_API_KEY", raising=False)
    monkeypatch.delenv("PAIN001_ALLOWED_HOSTS", raising=False)


def _get(headers: dict[str, str]) -> int:
    return (
        TestClient(app, base_url=LOCAL)
        .get(UNKNOWN_JOB, headers=headers)
        .status_code
    )


def test_a_foreign_host_is_refused():
    assert _get({"Host": "evil.example"}) == 400
    assert _get({"Host": "evil.example:8000"}) == 400


def test_a_foreign_origin_is_refused():
    assert _get({"Origin": "http://evil.example"}) == 403
    assert _get({"Origin": "null"}) == 403


def test_the_refusal_says_why():
    response = TestClient(app, base_url=LOCAL).get(
        UNKNOWN_JOB, headers={"Host": "evil.example"}
    )
    assert "PAIN001_API_KEY" in response.json()["detail"]
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1:8000",
        "127.0.0.2",
        "localhost:8000",
        "LOCALHOST",
        "[::1]:8000",
    ],
)
def test_loopback_hosts_are_served(host):
    assert _get({"Host": host}) == 404
    assert _get({"Host": host, "Origin": f"http://{host}"}) == 404


def test_a_key_lifts_the_check(monkeypatch):
    monkeypatch.setenv("PAIN001_API_KEY", "k")
    headers = {
        "Host": "pain001.internal",
        "Origin": "https://ui.example",
        "Authorization": "Bearer k",
    }
    assert _get(headers) == 404


def test_extra_hosts_can_be_named(monkeypatch):
    monkeypatch.setenv("PAIN001_ALLOWED_HOSTS", " Box.LAN , [fd00::1] ,")
    assert _get({"Host": "box.lan:8000"}) == 404
    assert _get({"Host": "[fd00::1]:8000"}) == 404
    assert _get({"Origin": "http://box.lan"}) == 404
    assert _get({"Host": "evil.example"}) == 400


def test_a_star_accepts_any_host(monkeypatch):
    monkeypatch.setenv("PAIN001_ALLOWED_HOSTS", "*")
    assert _get({"Host": "evil.example", "Origin": "http://x.example"}) == 404


@pytest.mark.parametrize(
    ("netloc", "expected"),
    [
        ("127.0.0.1:8000", "127.0.0.1"),
        ("[::1]:1", "::1"),
        ("Example.COM", "example.com"),
        ("", None),
        ("[::1", None),
        (":8000", None),
    ],
)
def test_hostname(netloc, expected):
    assert hostname(netloc) == expected


def test_allowed_host_refuses_what_it_cannot_parse():
    assert not allowed_host(None, frozenset())
    assert not allowed_host("evil.example", frozenset())
    assert allowed_host("127.255.0.1", frozenset())


def test_non_http_scopes_pass_through():
    """Lifespan events reach the application untouched."""
    with TestClient(app, base_url=LOCAL) as client:
        assert client.get(UNKNOWN_JOB).status_code == 404
