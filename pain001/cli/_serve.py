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

"""The ``pain001 serve`` command and its bind-address policy.

Without ``PAIN001_API_KEY`` the REST API has no authentication, so
``serve`` refuses to bind anything but loopback (decision D9) unless
the operator opts in with ``--insecure`` or ``PAIN001_ALLOW_INSECURE=1``.
"""

from __future__ import annotations

import ipaddress
import os
import sys

import click
from rich.console import Console

from pain001.cli._output import esc
from pain001.observability.otel import init_otel
from pain001.security.api_access import (
    API_KEY_ENV,
    INSECURE_ENV,
    insecure_allowed,
)

console = Console()


def is_loopback(host: str) -> bool:
    """Tell whether ``host`` names only the loopback interface.

    ``localhost`` is matched by name (no DNS lookup); addresses are
    parsed, so all of ``127.0.0.0/8`` and ``::1`` (bracketed or not)
    count. Anything else, the empty string and wildcards included, does
    not.

    Args:
        host: The ``--host`` value.

    Returns:
        True for a loopback-only bind.
    """
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def check_bind(host: str, insecure: bool) -> None:
    """Refuse an unauthenticated bind beyond loopback.

    Args:
        host: The address ``serve`` is about to bind.
        insecure: Whether ``--insecure`` was given.

    Raises:
        click.UsageError: Without an API key, on a non-loopback host,
            unless the operator opted in.
    """
    if os.environ.get(API_KEY_ENV) or is_loopback(host):
        return
    if insecure or insecure_allowed():
        console.print(
            f"[bold yellow]! Warning:[/bold yellow] serving on {esc(repr(host))} "
            f"unauthenticated: {API_KEY_ENV} is unset. Anyone who can "
            "reach this address can generate and download files."
        )
        return
    raise click.UsageError(
        f"refusing to serve on {host!r} without an API key. Set "
        f"{API_KEY_ENV} to require bearer auth, or, on a network you "
        f"trust, pass --insecure (or set {INSECURE_ENV}=1) to serve "
        "unauthenticated."
    )


@click.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for local development.",
)
@click.option(
    "--insecure",
    is_flag=True,
    default=False,
    help=(
        f"Allow a non-loopback --host without {API_KEY_ENV} "
        f"(same as {INSECURE_ENV}=1). For trusted networks only."
    ),
)
def serve_cmd(host: str, port: int, reload: bool, insecure: bool) -> None:
    """Launch the REST API with uvicorn (requires pain001[api]).
    \f
    Args:
        host: Interface address to bind.
        port: TCP port to listen on.
        reload: If True, enable uvicorn auto-reload.
        insecure: If True, allow a non-loopback host without an API key.
    """
    check_bind(host, insecure)
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[bold red]✗ Error:[/bold red] The REST API requires the 'api' "
            "extra. Install it with: [cyan]pip install pain001[api][/cyan]"
        )
        sys.exit(2)
    # Bootstrap tracing once per process (no-op unless OTEL_ENABLED).
    init_otel()
    console.print(
        f"[cyan]→ Serving pain001 REST API on http://{esc(host)}:{port}[/cyan]"
    )
    uvicorn.run(  # pragma: no cover - long-running server process
        "pain001.api.app:app", host=host, port=port, reload=reload
    )
