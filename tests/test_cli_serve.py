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

"""``pain001 serve`` refuses an open, unauthenticated, non-loopback bind.

Decision D9: without ``PAIN001_API_KEY`` the REST API has no auth, so
``serve`` binds only to loopback unless the operator opts in with
``--insecure`` or ``PAIN001_ALLOW_INSECURE=1``.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001.cli.cli import cli

_KEY = "PAIN001_API_KEY"
_ALLOW = "PAIN001_ALLOW_INSECURE"


@pytest.fixture(autouse=True)
def _no_auth_env(monkeypatch):
    """Start every test with neither variable set."""
    monkeypatch.delenv(_KEY, raising=False)
    monkeypatch.delenv(_ALLOW, raising=False)


def _serve(*args: str):
    """Invoke ``serve`` with uvicorn stubbed out.

    Args:
        *args: Extra ``serve`` arguments.

    Returns:
        The Click result and the uvicorn.run mock.
    """
    with patch("uvicorn.run") as run:
        result = CliRunner().invoke(cli, ["serve", *args])
    return result, run


@pytest.mark.parametrize(
    "host", ["0.0.0.0", "::", "192.0.2.10", "example.org", ""]
)
def test_open_bind_without_key_is_refused(host):
    """A non-loopback host with no key is a usage error naming both fixes."""
    result, run = _serve("--host", host)
    assert result.exit_code == 2, result.output
    assert _KEY in result.output
    assert "--insecure" in result.output
    assert f"{_ALLOW}=1" in result.output
    run.assert_not_called()


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.0.0.2", "::1", "[::1]", "localhost", "LocalHost"],
)
def test_loopback_needs_no_key(host):
    """Loopback binds stay allowed without a key."""
    result, run = _serve("--host", host)
    assert result.exit_code == 0, result.output
    assert run.call_args.kwargs["host"] == host


def test_default_host_is_loopback():
    """The default bind needs no key."""
    result, run = _serve()
    assert result.exit_code == 0, result.output
    assert run.call_args.kwargs["host"] == "127.0.0.1"


def test_open_bind_with_key_is_allowed(monkeypatch):
    """A configured API key permits a public bind."""
    monkeypatch.setenv(_KEY, "secret")
    result, run = _serve("--host", "0.0.0.0")
    assert result.exit_code == 0, result.output
    assert run.call_args.kwargs["host"] == "0.0.0.0"
    assert "unauthenticated" not in result.output


def test_insecure_flag_allows_open_bind_with_a_warning():
    """``--insecure`` opts in, and says what it opted into."""
    result, run = _serve("--host", "0.0.0.0", "--insecure")
    assert result.exit_code == 0, result.output
    run.assert_called_once()
    assert "unauthenticated" in result.output
    assert "PAIN001_ALLOWED_HOSTS" in result.output


@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_insecure_env_allows_open_bind(monkeypatch, value):
    """``PAIN001_ALLOW_INSECURE`` is the flag's environment twin."""
    monkeypatch.setenv(_ALLOW, value)
    result, run = _serve("--host", "0.0.0.0")
    assert result.exit_code == 0, result.output
    run.assert_called_once()
    assert "unauthenticated" in result.output


@pytest.mark.parametrize("value", ["0", "", "no"])
def test_falsy_insecure_env_still_refuses(monkeypatch, value):
    """Only an explicit truthy value opts in."""
    monkeypatch.setenv(_ALLOW, value)
    result, run = _serve("--host", "0.0.0.0")
    assert result.exit_code == 2, result.output
    run.assert_not_called()


def test_app_warns_at_startup_without_a_key(caplog):
    """Started by uvicorn directly, the app says it is unauthenticated."""
    from pain001.api.app import app

    with caplog.at_level(logging.WARNING), TestClient(app):
        pass
    assert any(_KEY in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(("name", "value"), [(_KEY, "secret"), (_ALLOW, "1")])
def test_app_is_quiet_when_auth_is_decided(monkeypatch, caplog, name, value):
    """A key, or an explicit opt-out, silences the start-up warning."""
    from pain001.api.app import app

    monkeypatch.setenv(name, value)
    with caplog.at_level(logging.WARNING), TestClient(app):
        pass
    assert not any(_KEY in r.getMessage() for r in caplog.records)
