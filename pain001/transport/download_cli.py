# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``pain001 download``: fetch a bank's replies over SFTP, each once.

Paramiko is imported only when the command runs, so the base install
(without ``pain001[upload]``) still lists it and explains the extra.
"""

from __future__ import annotations

from typing import Any

import click

from pain001.cli._format import emit_json, format_option
from pain001.transport.cli import ssh_kwargs, ssh_options


def _shown(name: str) -> str:
    r"""A remote name made safe for a terminal.

    Names come from the server. Backslashes and anything not printable
    (C0 and C1 controls, DEL, bidirectional overrides) are written as
    ``\xNN`` or ``\uNNNN`` so a hostile name cannot move the cursor,
    retitle the window or disguise itself.
    """
    return "".join(
        char
        if char.isprintable() and char != "\\"
        else f"\\x{ord(char):02x}"
        if ord(char) < 256
        else f"\\u{ord(char):04x}"
        for char in name
    )


def _report_json(result: Any) -> None:
    """Write the run as one JSON object: files, skipped, remaining.

    Remote names are written as JSON strings, which escape control
    characters, so they need no :func:`_shown`.

    Args:
        result: The ``DownloadResult``.
    """
    emit_json(
        {
            "files": [
                {
                    "remote": f.remote,
                    "local": f.local,
                    "sha256": f.sha256,
                    "size": f.size,
                    "status": f.status,
                }
                for f in result.files
            ],
            "skipped": list(result.skipped),
            "remaining": result.remaining,
        }
    )


def _report(result: Any) -> None:
    """Print one line per file, the skipped names and what was left."""
    for fetched in result.files:
        remote = _shown(fetched.remote)
        if fetched.status == "saved":
            click.echo(f"Saved: {remote} -> {fetched.local}")
        else:
            click.echo(f"Known: {remote} ({fetched.local})")
    for name in result.skipped:
        click.echo(f"Skipped: {_shown(name)}", err=True)
    if result.remaining:
        click.echo(f"{result.remaining} left for the next run", err=True)


@click.command("download")
@click.option(
    "--sftp",
    "url",
    required=True,
    help="Remote directory: sftp://user@host/outbox/ (trailing slash).",
)
@click.option(
    "--to",
    "to_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Existing local directory to save files into.",
)
@click.option(
    "--pattern", default="*", show_default=True, help="Filename glob."
)
@click.option(
    "--after-fetch",
    default="keep",
    show_default=True,
    help="keep, delete, or move:/absolute/dir for the remote copy.",
)
@click.option(
    "--settle-seconds",
    type=click.FloatRange(min=0, max=3600),
    default=0,
    show_default=True,
    help="Skip files whose size or mtime changes over this many seconds.",
)
@click.option(
    "--max-files",
    type=click.IntRange(min=1),
    default=1000,
    show_default=True,
    help="Most files one run fetches.",
)
@click.option(
    "--max-bytes",
    type=click.IntRange(min=1),
    default=256 * 1024 * 1024,
    show_default=True,
    help="Most bytes one run fetches.",
)
@click.option(
    "--ledger",
    type=click.Path(dir_okay=False),
    help="Ledger database (default: .pain001-ledger.sqlite3 in --to).",
)
@ssh_options
@format_option()
def download_cmd(
    url: str, to_dir: str, ledger: str | None, **flags: Any
) -> None:
    """Fetch new files from an SFTP directory, each exactly once.

    The host key is checked before any credential is sent. A file is
    saved, recorded in the ledger, and only then deleted or moved on the
    server. Schedule it with cron or a systemd timer; it runs once.
    \f
    Args:
        url: Remote directory URL.
        to_dir: Local directory.
        ledger: Optional ledger path.
        **flags: The policy flags, ``output_format`` and the shared trust
            and identity flags.

    Raises:
        click.ClickException: If the extra is missing or the run fails.
    """
    try:
        from paramiko import SSHException  # noqa: PLC0415

        import pain001.transport.download as download  # noqa: PLC0415
    except ImportError as exc:
        raise click.ClickException(
            "SFTP requires the optional dependencies; install "
            "'pain001[upload]'."
        ) from exc
    output_format = flags.pop("output_format")
    policy = download.DownloadPolicy(
        pattern=flags.pop("pattern"),
        after_fetch=flags.pop("after_fetch"),
        settle_seconds=flags.pop("settle_seconds"),
        max_files=flags.pop("max_files"),
        max_bytes=flags.pop("max_bytes"),
    )
    try:
        result = download.download_sftp(
            url, to_dir, policy=policy, ledger_path=ledger, **ssh_kwargs(flags)
        )
    except (OSError, ValueError, SSHException) as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        _report_json(result)
    else:
        _report(result)
