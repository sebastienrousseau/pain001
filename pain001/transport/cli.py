# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Click entry point for explicit SFTP uploads and host-key inspection."""

from __future__ import annotations

import os
from types import ModuleType

import click


def _secret_from_env(name: str | None) -> str | None:
    """Read a requested secret without including its value in diagnostics."""
    if name is None:
        return None
    value = os.environ.get(name)
    if not value:
        raise click.ClickException(
            f"Environment variable {name!r} is not set or is empty."
        )
    return value


def _transport() -> ModuleType:
    """Import the SFTP transport, or explain which extra provides it."""
    try:
        import pain001.transport.sftp as sftp  # noqa: PLC0415
    except ImportError as exc:
        raise click.ClickException(
            "SFTP requires the optional dependencies; install 'pain001[upload]'."
        ) from exc
    return sftp


def _print_host_key(transport: ModuleType, url: str, timeout: float) -> None:
    """Print a server's unverified host-key fingerprint, with a warning."""
    click.echo(transport.print_host_fingerprint(url, timeout))
    click.echo(
        "Unverified host key: compare this fingerprint with the bank's independently supplied value before trusting it.",
        err=True,
    )


@click.command("upload")
@click.argument(
    "file_path", required=False, type=click.Path(exists=True, dir_okay=False)
)
@click.option(
    "--sftp",
    "url",
    required=True,
    help="Destination: sftp://user@host/inbox/ or an explicit filename.",
)
@click.option(
    "--known-hosts",
    type=click.Path(exists=True, dir_okay=False),
    help="Trusted SSH known_hosts file.",
)
@click.option(
    "--accept-host-key",
    help="Independently verified OpenSSH SHA256 fingerprint; never saves trust.",
)
@click.option(
    "--identity-file",
    type=click.Path(exists=True, dir_okay=False),
    help="SSH private key; otherwise use the agent or default SSH keys.",
)
@click.option(
    "--certificate",
    type=click.Path(exists=True, dir_okay=False),
    help="OpenSSH certificate (*-cert.pub) issued for --identity-file.",
)
@click.option(
    "--use-agent",
    is_flag=True,
    help="Also offer ssh-agent keys (hardware keys) with a key or password.",
)
@click.option(
    "--password-env", help="Environment variable containing the SSH password."
)
@click.option(
    "--passphrase-env",
    help="Environment variable containing the private-key passphrase.",
)
@click.option(
    "--print-host-key",
    is_flag=True,
    help="Print the unverified fingerprint without authenticating or uploading.",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1, max=300),
    default=15,
    show_default=True,
    help="Network timeout in seconds.",
)
def upload_cmd(
    file_path: str | None,
    url: str,
    known_hosts: str | None,
    accept_host_key: str | None,
    identity_file: str | None,
    certificate: str | None,
    use_agent: bool,
    password_env: str | None,
    passphrase_env: str | None,
    print_host_key: bool,
    timeout: float,
) -> None:
    """Deliver FILE_PATH atomically to an explicitly trusted SFTP server.
    \f
    Args:
        file_path: Local payment file; omitted only for host-key inspection.
        url: Destination SFTP URL.
        known_hosts: Optional trusted host-key file.
        accept_host_key: Independently verified SHA256 fingerprint.
        identity_file: Optional SSH private key.
        certificate: Optional OpenSSH certificate for the private key.
        use_agent: Offer ssh-agent keys alongside a key or password.
        password_env: Name of the SSH-password environment variable.
        passphrase_env: Name of the key-passphrase environment variable.
        print_host_key: Observe a host key without authentication.
        timeout: Network timeout in seconds.

    Raises:
        click.ClickException: If dependencies, secrets or the transfer fail.
        click.UsageError: If no file was supplied for an upload.
    """
    transport = _transport()
    try:
        if print_host_key:
            _print_host_key(transport, url, timeout)
            return
        if file_path is None:
            raise click.UsageError(
                "FILE_PATH is required unless --print-host-key is used."
            )
        result = transport.upload_sftp(
            file_path,
            url,
            known_hosts=known_hosts,
            accept_host_key=accept_host_key,
            identity_file=identity_file,
            password=_secret_from_env(password_env),
            passphrase=_secret_from_env(passphrase_env),
            certificate=certificate,
            use_agent=use_agent,
            timeout=timeout,
        )
        action = "Already delivered" if result.reused else "Uploaded"
        click.echo(f"{action}: {result.destination} (SHA256 {result.sha256})")
    except (OSError, ValueError, transport.paramiko.SSHException) as exc:
        raise click.ClickException(str(exc)) from exc
