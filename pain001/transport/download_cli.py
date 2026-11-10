# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``pain001 download``: fetch a bank's replies over SFTP, each once.

Paramiko is imported only when the command runs, so the base install
(without ``pain001[upload]``) still lists it and explains the extra.
"""

from __future__ import annotations

from typing import Any

import click

from pain001.transport.cli import ssh_kwargs, ssh_options


def _report(result: Any) -> None:
    """Print one line per file, the skipped names and what was left."""
    for fetched in result.files:
        if fetched.status == "saved":
            click.echo(f"Saved: {fetched.remote} -> {fetched.local}")
        else:
            click.echo(f"Known: {fetched.remote} ({fetched.local})")
    for name in result.skipped:
        click.echo(f"Skipped: {name}", err=True)
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
        **flags: The policy flags and the shared trust and identity flags.

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
    _report(result)
