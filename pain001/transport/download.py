# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Exactly-once SFTP downloads of a bank's replies.

Each listed file is read into a private temporary file in the target
directory and hashed. A file the ledger already holds is not saved
again; a new one is moved into place under its own name, or beside it
as ``name.<sha8>.ext`` when different bytes already hold that name.
The ledger row is committed before the remote copy is deleted or
moved, so an interrupted run never loses a file and never saves one
twice. The connection is the same audited one ``upload`` uses.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import paramiko

from pain001.transport.ledger import Entry, Ledger
from pain001.transport.sftp import (
    Credentials,
    SFTPTarget,
    Trust,
    parse_target,
    session,
)

_BLOCK_SIZE = 65536
LEDGER_NAME = ".pain001-ledger.sqlite3"
Listed = tuple[str, int, int]


@dataclass(frozen=True)
class DownloadPolicy:
    """What to fetch, what to do with the remote copy, and the limits.

    ``after_fetch`` is ``keep``, ``delete`` or ``move:/absolute/dir``.
    ``settle_seconds`` lists twice that far apart and skips files whose
    size or mtime changed, so a file the bank is still writing waits
    for the next run. The caps bound one run; files over them stay on
    the server for the next.
    """

    pattern: str = "*"
    after_fetch: str = "keep"
    settle_seconds: float = 0
    max_files: int = 1000
    max_bytes: int = 256 * 1024 * 1024


@dataclass(frozen=True)
class Fetched:
    """One remote file this run handled.

    ``status`` is ``saved`` (written locally now) or ``known`` (the
    ledger already held these bytes, so nothing was written).
    """

    remote: str
    local: str
    sha256: str
    size: int
    status: str


@dataclass(frozen=True)
class DownloadResult:
    """What a run fetched, what it skipped and what the caps left."""

    files: tuple[Fetched, ...]
    skipped: tuple[str, ...] = ()
    remaining: int = 0


@dataclass
class _Run:
    """Per-run state shared by the steps of one download."""

    sftp: paramiko.SFTPClient
    target: SFTPTarget
    local: Path
    ledger: Ledger
    disposal: tuple[str, str | None]
    budget: int
    files: list[Fetched] = field(default_factory=list)

    def source(self, name: str) -> str:
        """The ledger key for a remote file."""
        t = self.target
        return f"{t.username}@{t.host}:{t.port}{t.path}{name}"


def parse_after_fetch(value: str) -> tuple[str, str | None]:
    """Parse ``keep``, ``delete`` or ``move:/absolute/dir``.

    Args:
        value: The ``--after-fetch`` value.

    Returns:
        The action and, for ``move``, the archive directory without a
        trailing slash.

    Raises:
        ValueError: For any other value, or an unsafe archive path.
    """
    if value in ("keep", "delete"):
        return value, None
    directory = value.removeprefix("move:").rstrip("/")
    if (
        not value.startswith("move:")
        or not directory.startswith("/")
        or any(part in {".", ".."} for part in directory.split("/"))
        or not _printable(directory)
    ):
        raise ValueError(
            "--after-fetch must be keep, delete or move:/absolute/dir."
        )
    return "move", directory


def _printable(text: str) -> bool:
    """True when ``text`` has no control characters."""
    return all(32 <= ord(char) != 127 for char in text)


def _safe_name(name: str) -> bool:
    """A flat, visible, finished filename: no paths, dots or temp files."""
    return (
        _printable(name)
        and "/" not in name
        and "\\" not in name
        and not name.startswith(".")
        and not name.endswith((".tmp", ".part"))
    )


def _list(
    sftp: paramiko.SFTPClient, directory: str, pattern: str
) -> tuple[list[Listed], list[str]]:
    """List regular files matching ``pattern``; name the ones refused.

    Symlinks, directories and unsafe or temporary names are skipped and
    returned, so a link on the server can never point the download at
    another file.
    """
    files: list[Listed] = []
    skipped: list[str] = []
    for attrs in sftp.listdir_attr(directory):
        name = attrs.filename
        if not fnmatch.fnmatchcase(name, pattern):
            continue
        mode = attrs.st_mode or 0
        if not (stat.S_ISREG(mode) and _safe_name(name)):
            skipped.append(name)
            continue
        files.append((name, attrs.st_size or 0, int(attrs.st_mtime or 0)))
    return sorted(files), skipped


def _settled(
    run: _Run,
    listed: list[Listed],
    pattern: str,
    wait: tuple[float, Callable[[float], None]],
) -> tuple[list[Listed], list[str]]:
    """Keep the files whose size and mtime did not move during ``wait``."""
    seconds, sleep = wait
    if seconds <= 0:
        return listed, []
    sleep(seconds)
    again = set(_list(run.sftp, run.target.path, pattern)[0])
    steady = [item for item in listed if item in again]
    moving = [item[0] for item in listed if item not in again]
    return steady, moving


def _receive(run: _Run, name: str, size: int) -> tuple[Path, str]:
    """Read one remote file into a private temporary file and hash it.

    The temporary file is removed again if anything interrupts the
    transfer.

    Args:
        run: This run's connection and local directory.
        name: The remote filename.
        size: Its listed size in bytes.

    Returns:
        The temporary file and the SHA256 of what was read.

    Raises:
        OSError: If the file's size differs from its listing.
        BaseException: Any interruption, after removing the temporary.
    """
    descriptor, temporary = tempfile.mkstemp(
        prefix=".pain001-", suffix=".part", dir=run.local
    )
    path = Path(temporary)
    digest, received = hashlib.sha256(), 0
    try:
        with os.fdopen(descriptor, "wb") as out:
            with run.sftp.open(run.target.path + name, "rb") as remote:
                for block in iter(lambda: remote.read(_BLOCK_SIZE), b""):
                    received += len(block)
                    if received > size:
                        break
                    digest.update(block)
                    out.write(block)
            out.flush()
            os.fsync(out.fileno())
        if received != size:
            raise OSError(f"{name} changed size during the download; retry.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path, digest.hexdigest()


def _file_sha256(path: Path) -> str:
    """Hash a local file in bounded blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def _place(
    temporary: Path, directory: Path, name: str, sha256: str
) -> tuple[Path, bool]:
    """Move a received file to ``name``, or ``name.<sha8>.ext`` beside it.

    Args:
        temporary: The received file.
        directory: The local download directory.
        name: The remote filename.
        sha256: The received bytes' SHA256.

    Returns:
        Where the bytes now live, and False when an identical file was
        already there (a ledger lost or kept elsewhere).

    Raises:
        FileExistsError: If both names hold different bytes.
    """
    stem, suffix = os.path.splitext(name)
    for candidate in (name, f"{stem}.{sha256[:8]}{suffix}"):
        final = directory / candidate
        if not final.exists() and not final.is_symlink():
            os.replace(temporary, final)
            return final, True
        if final.is_file() and _file_sha256(final) == sha256:
            temporary.unlink()
            return final, False
    temporary.unlink()
    raise FileExistsError(
        f"{name} and its {sha256[:8]} variant already hold other bytes."
    )


def _dispose(run: _Run, name: str) -> None:
    """Delete or move the remote copy, as the policy says."""
    action, archive = run.disposal
    remote = run.target.path + name
    if action == "delete":
        run.sftp.remove(remote)
    else:
        run.sftp.rename(remote, f"{archive}/{name}")


def _fetch(run: _Run, item: Listed) -> bool:
    """Save one file at most once, then dispose of the remote copy.

    Args:
        run: This run's connection, ledger, policy and budget.
        item: The file's name, listed size and listed mtime.

    Returns:
        False when the byte budget stops the run before this file.
    """
    name, size, mtime = item
    source = run.source(name)
    entry = run.ledger.known(source, size, mtime)
    status = "known"
    if entry is None:
        if size > run.budget:
            return False
        run.budget -= size
        temporary, sha256 = _receive(run, name, size)
        entry = run.ledger.find(source, sha256)
        if entry is None:
            final, wrote = _place(temporary, run.local, name, sha256)
            entry = Entry(source, sha256, size, mtime, str(final))
            run.ledger.record(entry)
            status = "saved" if wrote else "known"
        else:
            temporary.unlink()
    if run.disposal[0] != "keep":
        _dispose(run, name)
        run.ledger.mark_disposed(entry)
    run.files.append(
        Fetched(
            run.target.path + name,
            entry.local_path,
            entry.sha256,
            size,
            status,
        )
    )
    return True


def _check_inputs(
    target: SFTPTarget, local: Path, policy: DownloadPolicy
) -> tuple[str, str | None]:
    """Refuse a non-directory URL, a missing directory or bad limits."""
    if not target.path.endswith("/"):
        raise ValueError("Download from a directory URL ending in '/'.")
    if local.is_symlink() or not local.is_dir():
        raise ValueError(f"--to must be an existing directory: {local}")
    if policy.max_files < 1 or policy.max_bytes < 1:
        raise ValueError("max_files and max_bytes must be at least 1.")
    if policy.settle_seconds < 0:
        raise ValueError("settle_seconds must not be negative.")
    return parse_after_fetch(policy.after_fetch)


def download_sftp(
    url: str,
    to_dir: str,
    *,
    policy: DownloadPolicy | None = None,
    ledger_path: str | None = None,
    known_hosts: str | None = None,
    accept_host_key: str | None = None,
    identity_file: str | None = None,
    password: str | None = None,
    passphrase: str | None = None,
    certificate: str | None = None,
    use_agent: bool = False,
    timeout: float = 15,
    sleep: Callable[[float], None] = time.sleep,
) -> DownloadResult:
    """Fetch a remote directory's files into ``to_dir``, each exactly once.

    The host key is checked before any credential is sent, as for
    ``upload_sftp``. Files are saved 0600; the ledger (in ``to_dir``
    unless ``ledger_path`` names another) is committed before the remote
    copy is deleted or moved. paramiko.SSHException, OSError and
    FileExistsError propagate. No daemon: schedule it with cron.

    Args:
        url: ``sftp://user@host[:port]/remote/dir/`` (trailing slash).
        to_dir: Existing local directory to save into.
        policy: Pattern, disposal, settle time and caps.
        ledger_path: Ledger database; defaults inside ``to_dir``.
        known_hosts: Explicit known_hosts file.
        accept_host_key: Independently verified SHA256 fingerprint.
        identity_file: Optional private key filename.
        password: Optional password, never logged.
        passphrase: Optional private-key passphrase, never logged.
        certificate: Optional OpenSSH certificate for ``identity_file``.
        use_agent: Also offer ssh-agent keys.
        timeout: Network operation timeout in seconds.
        sleep: How to wait out ``settle_seconds`` (tests replace it).

    Returns:
        The files handled, the names skipped and how many the caps left.
    """
    policy = policy or DownloadPolicy()
    target, local = parse_target(url), Path(to_dir)
    disposal = _check_inputs(target, local, policy)
    trust = Trust(known_hosts, accept_host_key)
    credentials = Credentials(
        identity_file, certificate, password, passphrase, use_agent
    )
    ledger_file = Path(ledger_path) if ledger_path else local / LEDGER_NAME
    with (
        Ledger(ledger_file) as ledger,
        session(target, trust, credentials, timeout) as sftp,
    ):
        run = _Run(sftp, target, local, ledger, disposal, policy.max_bytes)
        return _fetch_all(run, policy, sleep)


def _fetch_all(
    run: _Run, policy: DownloadPolicy, sleep: Callable[[float], None]
) -> DownloadResult:
    """List, settle and fetch within the caps; report what was left.

    Args:
        run: This run's connection, ledger, disposal and byte budget.
        policy: Pattern, settle time and file cap.
        sleep: How to wait out the settle time.

    Returns:
        The files handled, the names skipped and how many remain.
    """
    listed, skipped = _list(run.sftp, run.target.path, policy.pattern)
    wait = (policy.settle_seconds, sleep)
    listed, moving = _settled(run, listed, policy.pattern, wait)
    handled = 0
    for item in listed[: policy.max_files]:
        if not _fetch(run, item):
            break
        handled += 1
    return DownloadResult(
        tuple(run.files), tuple(skipped + moving), len(listed) - handled
    )
