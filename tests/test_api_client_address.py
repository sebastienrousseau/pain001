# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The rate limiter keys on the client, not on the proxy in front of it.

Audit finding S14: behind a reverse proxy every request arrives from the
proxy's socket address, so one bucket covers every client. A forwarded
address is honoured only when the immediate peer is a configured trusted
proxy, and the key is the right-most hop that is not one.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pain001.api.client_address import (  # noqa: E402
    ClientAddressResolver,
    forwarded_header_from_env,
    forwarded_hops,
    parse_trusted_proxies,
)
from pain001.api.ratelimit import install_rate_limiting  # noqa: E402


def _app(monkeypatch: pytest.MonkeyPatch, trusted: str | None) -> FastAPI:
    """Build an app limited to one request a minute per client."""
    monkeypatch.setenv("PAIN001_RATE_LIMIT", "1/minute")
    monkeypatch.delenv("PAIN001_RATE_LIMIT_BACKEND", raising=False)
    monkeypatch.delenv("PAIN001_FORWARDED_HEADER", raising=False)
    if trusted is None:
        monkeypatch.delenv("PAIN001_TRUSTED_PROXIES", raising=False)
    else:
        monkeypatch.setenv("PAIN001_TRUSTED_PROXIES", trusted)
    fresh = FastAPI()

    @fresh.get("/ping")
    def ping() -> dict[str, str]:
        """Answer every request."""
        return {"ok": "yes"}

    install_rate_limiting(fresh)
    return fresh


def _status(client: TestClient, forwarded_for: str) -> int:
    """Send one request carrying ``X-Forwarded-For``."""
    return client.get(
        "/ping", headers={"X-Forwarded-For": forwarded_for}
    ).status_code


def test_trusted_proxy_clients_get_their_own_bucket(monkeypatch) -> None:
    """Two clients behind one trusted proxy are limited separately."""
    client = TestClient(
        _app(monkeypatch, "10.0.0.0/8"), client=("10.0.0.1", 1234)
    )
    assert _status(client, "198.51.100.7") == 200
    assert _status(client, "203.0.113.9") == 200
    assert _status(client, "198.51.100.7") == 429


def test_untrusted_peer_cannot_spoof_its_key(monkeypatch) -> None:
    """Without a trusted proxy the header is ignored: no bucket escape."""
    client = TestClient(_app(monkeypatch, None), client=("10.0.0.1", 1234))
    assert _status(client, "198.51.100.7") == 200
    assert _status(client, "203.0.113.9") == 429


def test_client_cannot_prepend_a_forged_hop(monkeypatch) -> None:
    """A hop the client writes before the proxy's own is never the key."""
    client = TestClient(
        _app(monkeypatch, "10.0.0.0/8"), client=("10.0.0.1", 1234)
    )
    assert _status(client, "1.1.1.1, 198.51.100.7") == 200
    assert _status(client, "2.2.2.2, 198.51.100.7") == 429


# ---------------------------------------------------------------------------
# The resolver itself
# ---------------------------------------------------------------------------
def _scope(peer: str | None, *headers: tuple[str, str]) -> dict:
    """Build an HTTP scope from a peer address and raw headers."""
    return {
        "type": "http",
        "client": (peer, 1234) if peer else None,
        "headers": [(k.encode(), v.encode()) for k, v in headers],
    }


def test_parse_trusted_proxies_accepts_addresses_and_networks() -> None:
    """Addresses become one-host networks; blanks are skipped."""
    nets = parse_trusted_proxies(" 10.0.0.0/8, ,192.0.2.10,::1 ")
    assert [str(n) for n in nets] == ["10.0.0.0/8", "192.0.2.10/32", "::1/128"]
    assert parse_trusted_proxies("") == ()


def test_parse_trusted_proxies_rejects_a_bad_entry() -> None:
    """A name that is not an address stops start-up."""
    with pytest.raises(ValueError, match="PAIN001_TRUSTED_PROXIES"):
        parse_trusted_proxies("10.0.0.0/8, proxy.internal")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", "x-forwarded-for"), ("Forwarded", "forwarded")],
)
def test_forwarded_header_from_env(monkeypatch, raw, expected) -> None:
    """The header defaults to ``X-Forwarded-For``."""
    monkeypatch.setenv("PAIN001_FORWARDED_HEADER", raw)
    assert forwarded_header_from_env() == expected


def test_forwarded_header_from_env_rejects_others(monkeypatch) -> None:
    """Only the two forwarded headers are accepted."""
    monkeypatch.setenv("PAIN001_FORWARDED_HEADER", "x-real-ip")
    with pytest.raises(ValueError, match="PAIN001_FORWARDED_HEADER"):
        forwarded_header_from_env()


def test_forwarded_hops_parses_both_headers() -> None:
    """Ports, quotes and IPv6 brackets are stripped; empty hops dropped."""
    assert forwarded_hops(
        ["198.51.100.7:4711, ,10.0.0.2", "10.0.0.3"], "x-forwarded-for"
    ) == ["198.51.100.7", "10.0.0.2", "10.0.0.3"]
    assert forwarded_hops(
        ['for="[2001:db8::1]:4711";proto=https, proto=http, For=10.0.0.2'],
        "forwarded",
    ) == ["2001:db8::1", "10.0.0.2"]


def test_resolver_from_env(monkeypatch) -> None:
    """The environment names the networks and the header."""
    monkeypatch.setenv("PAIN001_TRUSTED_PROXIES", "10.0.0.0/8")
    monkeypatch.setenv("PAIN001_FORWARDED_HEADER", "forwarded")
    resolver = ClientAddressResolver.from_env()
    assert resolver.header == "forwarded"
    assert resolver.is_trusted("10.1.2.3")
    assert not resolver.is_trusted("unknown")


@pytest.mark.parametrize(
    ("peer", "headers", "expected"),
    [
        (None, (), "unknown"),
        ("testclient", (("x-forwarded-for", "1.2.3.4"),), "testclient"),
        ("10.0.0.1", (), "10.0.0.1"),
        ("10.0.0.1", (("x-forwarded-for", "10.0.0.5, 10.0.0.6"),), "10.0.0.5"),
        (
            "10.0.0.1",
            (("x-forwarded-for", "9.9.9.9, 198.51.100.7, 10.0.0.6"),),
            "198.51.100.7",
        ),
        ("10.0.0.1", (("x-forwarded-for", "unknown"),), "unknown"),
    ],
)
def test_resolver_picks_the_right_most_untrusted_hop(
    peer, headers, expected
) -> None:
    """Only a trusted peer's header counts, read right to left."""
    networks = parse_trusted_proxies("10.0.0.0/8")
    scope = _scope(peer, *headers)
    assert ClientAddressResolver(networks).resolve(scope) == expected


def test_resolver_with_no_trusted_proxy_ignores_the_header() -> None:
    """The default resolver keys on the socket address."""
    scope = _scope("10.0.0.1", ("x-forwarded-for", "198.51.100.7"))
    assert ClientAddressResolver().resolve(scope) == "10.0.0.1"


def test_resolver_reads_only_the_configured_header() -> None:
    """With ``forwarded`` chosen, ``X-Forwarded-For`` is not read."""
    resolver = ClientAddressResolver(
        parse_trusted_proxies("10.0.0.0/8"), "forwarded"
    )
    scope = _scope(
        "10.0.0.1",
        ("x-forwarded-for", "9.9.9.9"),
        ("forwarded", "for=198.51.100.7"),
    )
    assert resolver.resolve(scope) == "198.51.100.7"
