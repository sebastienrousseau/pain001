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

"""The client address of a request, through trusted proxies only.

Behind a reverse proxy every request arrives from the proxy's socket
address, so a limiter keyed on it puts every client in one bucket. The
proxy names the real client in ``X-Forwarded-For`` (or the standard
``Forwarded`` header), but any client can send that header too, so it is
read only when the immediate peer is in ``PAIN001_TRUSTED_PROXIES``.

``PAIN001_TRUSTED_PROXIES`` is a comma-separated list of addresses or
networks (``10.0.0.0/8, 192.0.2.10``); empty by default, which ignores
every forwarded header. ``PAIN001_FORWARDED_HEADER`` picks the one header
the proxy writes, ``x-forwarded-for`` (default) or ``forwarded``; reading
a header the proxy passes through untouched would let a client choose its
own address. The client is the right-most hop that is not itself a
trusted proxy: every hop to its left was written by that client.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Iterable

from starlette.datastructures import Headers
from starlette.types import Scope

TRUSTED_PROXIES_ENV = "PAIN001_TRUSTED_PROXIES"
"""Comma-separated addresses or networks whose forwarded header counts."""

FORWARDED_HEADER_ENV = "PAIN001_FORWARDED_HEADER"
"""The header the trusted proxy writes: ``x-forwarded-for`` or ``forwarded``."""

_HEADERS = ("x-forwarded-for", "forwarded")

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_trusted_proxies(raw: str) -> tuple[Network, ...]:
    """Parse a comma-separated list of proxy addresses or networks.

    Args:
        raw: For example ``"10.0.0.0/8, 192.0.2.10, ::1"``.

    Returns:
        One network per entry; an address is a one-host network.

    Raises:
        ValueError: If an entry is not an address or a network.
    """
    networks: list[Network] = []
    for entry in (part.strip() for part in raw.split(",")):
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError as exc:
            raise ValueError(
                f"{TRUSTED_PROXIES_ENV}: {entry!r} is not an IP address "
                "or network"
            ) from exc
    return tuple(networks)


def forwarded_header_from_env() -> str:
    """Return the forwarded header ``PAIN001_FORWARDED_HEADER`` names.

    Returns:
        ``x-forwarded-for`` (the default) or ``forwarded``.

    Raises:
        ValueError: If the variable names any other header.
    """
    raw = os.environ.get(FORWARDED_HEADER_ENV, "").strip().lower()
    header = raw or _HEADERS[0]
    if header not in _HEADERS:
        raise ValueError(
            f"{FORWARDED_HEADER_ENV} must be 'x-forwarded-for' or "
            f"'forwarded', got {raw!r}"
        )
    return header


def _host(node: str) -> str:
    """Strip quotes, brackets and a port from one forwarded hop.

    Args:
        node: A hop such as ``192.0.2.1``, ``"192.0.2.1:4711"`` or
            ``"[2001:db8::1]:4711"``.

    Returns:
        The bare host part.
    """
    node = node.strip().strip('"')
    if node.startswith("["):
        return node[1:].partition("]")[0]
    if node.count(":") == 1:
        return node.partition(":")[0]
    return node


def _forwarded_for(element: str) -> str | None:
    """Return the ``for=`` node of one ``Forwarded`` element, if any.

    Args:
        element: One comma-separated element, ``for=...;proto=https``.

    Returns:
        The node value, or ``None`` when the element has no ``for``.
    """
    for pair in element.split(";"):
        name, _, value = pair.partition("=")
        if name.strip().lower() == "for":
            return value
    return None


def forwarded_hops(values: Iterable[str], header: str) -> list[str]:
    """List the hosts a forwarded header names, client first.

    Args:
        values: Every value of the header, in the order received.
        header: ``x-forwarded-for`` or ``forwarded``.

    Returns:
        The bare hosts, left to right.
    """
    elements = [e for value in values for e in value.split(",")]
    if header == "forwarded":
        nodes = [_forwarded_for(element) for element in elements]
        elements = [node for node in nodes if node is not None]
    return [host for host in map(_host, elements) if host]


class ClientAddressResolver:
    """Find a request's client address, trusting only named proxies.

    Args:
        trusted: Networks whose forwarded header is believed. Empty
            (the default) means the socket address is always the key.
        header: The forwarded header those proxies write.
    """

    def __init__(
        self,
        trusted: Iterable[Network] = (),
        header: str = _HEADERS[0],
    ) -> None:
        self.trusted = tuple(trusted)
        self.header = header

    @classmethod
    def from_env(cls) -> ClientAddressResolver:
        """Build a resolver from the two environment variables.

        Returns:
            The resolver ``PAIN001_TRUSTED_PROXIES`` and
            ``PAIN001_FORWARDED_HEADER`` describe.
        """
        return cls(
            parse_trusted_proxies(os.environ.get(TRUSTED_PROXIES_ENV, "")),
            forwarded_header_from_env(),
        )

    def is_trusted(self, host: str) -> bool:
        """Return whether ``host`` is one of the trusted proxies.

        Args:
            host: A bare address; anything else is never trusted.

        Returns:
            ``True`` when the address lies in a trusted network.
        """
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(address in network for network in self.trusted)

    def resolve(self, scope: Scope) -> str:
        """Return the client address of one HTTP request.

        Args:
            scope: The ASGI connection scope.

        Returns:
            The right-most forwarded hop that is not a trusted proxy
            when the peer is one; the left-most hop when every hop is
            trusted; otherwise the socket address, or ``"unknown"``.
        """
        client = scope.get("client")
        peer = client[0] if client else "unknown"
        if not self.trusted or not self.is_trusted(peer):
            return peer
        values = Headers(scope=scope).getlist(self.header)
        hops = forwarded_hops(values, self.header)
        for hop in reversed(hops):
            if not self.is_trusted(hop):
                return hop
        return hops[0] if hops else peer
