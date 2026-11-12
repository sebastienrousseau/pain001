# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Pinned-host SFTP uploads with atomic publication and retry detection."""

from __future__ import annotations

import base64
import errno
import hashlib
import hmac
import socket
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import paramiko

from pain001.transport._algorithms import DISABLED_ALGORITHMS
from pain001.transport.identity import load_identity

_BLOCK_SIZE = 65536


@dataclass(frozen=True)
class SFTPTarget:
    """Validated connection coordinates without embedded credentials."""

    host: str
    port: int
    username: str
    path: str


@dataclass(frozen=True)
class UploadResult:
    """Receipt for a published file or a byte-identical earlier upload."""

    destination: str
    sha256: str
    reused: bool


def parse_target(url: str) -> SFTPTarget:
    """Parse an SFTP URL, refusing passwords and ambiguous remote paths.

    Args:
        url: An ``sftp://user@host[:port]/absolute/path`` URL.

    Returns:
        Validated host, port, username and decoded POSIX path.

    Raises:
        ValueError: If the URL contains unsupported or unsafe components.
    """
    parts = urlsplit(url)
    if parts.scheme != "sftp" or not parts.hostname or not parts.username:
        raise ValueError("Use sftp://user@host/absolute/path.")
    if parts.password is not None or parts.query or parts.fragment:
        raise ValueError(
            "SFTP URLs must not contain passwords, queries or fragments."
        )
    username = unquote(parts.username)
    path = unquote(parts.path)
    if not path.startswith("/") or any(
        part in {".", ".."} for part in path.split("/")
    ):
        raise ValueError(
            "The remote path must be absolute and contain no traversal components."
        )
    if any(
        ord(char) < 32 or ord(char) == 127
        for char in username + path + parts.hostname
    ):
        raise ValueError(
            "SFTP coordinates must not contain control characters."
        )
    port = parts.port if parts.port is not None else 22
    if port == 0:
        raise ValueError("The SFTP port must be between 1 and 65535.")
    return SFTPTarget(parts.hostname, port, username, path)


def fingerprint(key: paramiko.PKey) -> str:
    """Return the OpenSSH SHA256 fingerprint of an SSH public host key."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _validate_fingerprint(value: str | None) -> None:
    """Reject malformed pins before establishing a network connection."""
    if value is None:
        return
    if not value.startswith("SHA256:") or len(value) != 50:
        raise ValueError("Use an OpenSSH SHA256 host-key fingerprint.")
    try:
        decoded = base64.b64decode(value[7:] + "=", validate=True)
    except ValueError as exc:
        raise ValueError("Invalid SHA256 host-key fingerprint.") from exc
    if (
        len(decoded) != 32
        or base64.b64encode(decoded).decode().rstrip("=") != value[7:]
    ):
        raise ValueError("Invalid SHA256 host-key fingerprint.")


class _PinnedHostPolicy(paramiko.MissingHostKeyPolicy):
    """Verify known-host entries and an optional explicit pin before auth."""

    def __init__(
        self, known_hosts: paramiko.HostKeys, pin: str | None
    ) -> None:
        self.known_hosts = known_hosts
        self.pin = pin

    def missing_host_key(
        self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey
    ) -> None:
        """Refuse changed or untrusted keys without writing known_hosts."""
        known = self.known_hosts.lookup(hostname)
        if known is not None and not self.known_hosts.check(hostname, key):
            raise paramiko.SSHException(
                "Host key mismatch; verify the bank's key independently before updating known_hosts."
            )
        if self.pin is not None:
            if not hmac.compare_digest(self.pin, fingerprint(key)):
                raise paramiko.SSHException(
                    "Host key mismatch with --accept-host-key; verify the fingerprint independently."
                )
        elif known is None:
            raise paramiko.SSHException(
                "Unknown host key; provision known_hosts or use --accept-host-key with an independently verified fingerprint."
            )


def _load_known_hosts(path: str | None) -> paramiko.HostKeys:
    """Load trusted keys without adding or changing any trust entries."""
    keys = paramiko.HostKeys()
    if path is not None:
        keys.load(path)
    else:
        for candidate in (
            Path("/etc/ssh/ssh_known_hosts"),
            Path.home() / ".ssh" / "known_hosts",
        ):
            if candidate.is_file():
                keys.load(str(candidate))
    return keys


def print_host_fingerprint(url: str, timeout: float = 15) -> str:
    """Observe a server's unverified host fingerprint without authenticating.

    Args:
        url: The SFTP server URL.
        timeout: Connection and SSH handshake timeout in seconds.

    Returns:
        An untrusted fingerprint to compare with an independent source.
    """
    target = parse_target(url)
    with socket.create_connection(
        (target.host, target.port), timeout=timeout
    ) as connection:
        with paramiko.Transport(
            connection, disabled_algorithms=DISABLED_ALGORITHMS
        ) as transport:
            transport.start_client(timeout=timeout)
            return fingerprint(transport.get_remote_server_key())


def _digest(stream: BinaryIO) -> str:
    """Hash a stream in bounded chunks."""
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(_BLOCK_SIZE), b""):
        digest.update(block)
    return digest.hexdigest()


def _remote_state(
    sftp: paramiko.SFTPClient, destination: str, digest: str, size: int
) -> bool | None:
    """Return a hash-match result, or None when no destination exists."""
    try:
        attrs = sftp.lstat(destination)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return None
        raise
    if (
        attrs.st_mode is None
        or not stat.S_ISREG(attrs.st_mode)
        or attrs.st_size != size
    ):
        return False
    received = 0
    remote_hash = hashlib.sha256()
    with sftp.open(destination, "rb") as remote:
        for block in iter(lambda: remote.read(_BLOCK_SIZE), b""):
            received += len(block)
            if received > size:
                return False
            remote_hash.update(block)
    return received == size and hmac.compare_digest(
        remote_hash.hexdigest(), digest
    )


@dataclass(frozen=True)
class Credentials:
    """How the client authenticates; secrets are never logged."""

    identity_file: str | None = None
    certificate: str | None = None
    password: str | None = None
    passphrase: str | None = None
    use_agent: bool = False

    def __repr__(self) -> str:
        """Name the identity file only; secrets stay out of tracebacks."""
        return (
            f"Credentials(identity_file={self.identity_file!r}, "
            f"use_agent={self.use_agent})"
        )


@dataclass(frozen=True)
class Trust:
    """Which host keys are trusted before any credential is sent."""

    known_hosts: str | None = None
    accept_host_key: str | None = None


def _prepare(
    file_path: str, url: str, accept_host_key: str | None, timeout: float
) -> tuple[SFTPTarget, Path, str]:
    """Validate the inputs and return the target, local file and filename.

    Args:
        file_path: Local file to deliver.
        url: Remote file URL, or a directory URL ending in a slash.
        accept_host_key: Optional OpenSSH SHA256 fingerprint to validate.
        timeout: Network timeout in seconds (validated by the caller).

    Returns:
        The parsed target, the local path and the remote filename.
    """
    target = parse_target(url)
    _validate_fingerprint(accept_host_key)
    local = Path(file_path)
    return target, local, _destination(target, local)


def _measure(source: BinaryIO) -> tuple[str, int]:
    """Return the file's SHA256 and size, leaving it rewound."""
    digest = _digest(source)
    size = source.tell()
    source.seek(0)
    return digest, size


def _destination(target: SFTPTarget, local: Path) -> str:
    """Return the remote filename, refusing control characters."""
    destination = (
        target.path + local.name if target.path.endswith("/") else target.path
    )
    if any(ord(char) < 32 or ord(char) == 127 for char in destination):
        raise ValueError(
            "The destination filename must not contain control characters."
        )
    return destination


def _pin_host(
    client: paramiko.SSHClient,
    known_hosts: str | None,
    accept_host_key: str | None,
) -> None:
    """Install the host-key policy before any credentials are sent."""
    # Keep SSHClient's own host-key stores empty so this policy checks
    # both existing trust and the explicit pin before credentials leave.
    client.set_missing_host_key_policy(
        _PinnedHostPolicy(_load_known_hosts(known_hosts), accept_host_key)
    )


def _connect(
    client: paramiko.SSHClient,
    target: SFTPTarget,
    credentials: Credentials,
    timeout: float,
) -> None:
    """Load the identity, then connect; the host check runs first.

    The agent and default key files are used when nothing explicit is
    given; ``use_agent`` keeps the agent in play alongside an identity
    file or password (hardware-backed keys reach paramiko that way).
    """
    pkey = load_identity(
        credentials.identity_file,
        credentials.passphrase,
        credentials.certificate,
    )
    unattended = (
        credentials.identity_file is None and credentials.password is None
    )
    client.connect(
        target.host,
        port=target.port,
        username=target.username,
        password=credentials.password,
        pkey=pkey,
        allow_agent=credentials.use_agent or unattended,
        look_for_keys=unattended,
        timeout=timeout,
        banner_timeout=timeout,
        auth_timeout=timeout,
        disabled_algorithms=DISABLED_ALGORITHMS,
    )


def _open_sftp(
    client: paramiko.SSHClient, timeout: float
) -> paramiko.SFTPClient:
    """Open the SFTP session and apply the network timeout to it."""
    sftp = client.open_sftp()
    channel = sftp.get_channel()
    if channel is None:
        sftp.close()
        raise paramiko.SSHException("SFTP session has no active channel.")
    channel.settimeout(timeout)
    return sftp


def _already_delivered(
    sftp: paramiko.SFTPClient, destination: str, digest: str, size: int
) -> bool:
    """Return True for a byte-identical earlier upload, False if absent.

    Args:
        sftp: Open SFTP session.
        destination: Remote filename.
        digest: SHA256 of the local file.
        size: Size of the local file in bytes.

    Returns:
        True when the destination already holds these exact bytes.

    Raises:
        FileExistsError: If different data already occupies the destination.
    """
    state = _remote_state(sftp, destination, digest, size)
    if state is False:
        raise FileExistsError(
            "Remote destination already contains different data; choose a new filename."
        )
    return state is True


def _publish(
    sftp: paramiko.SFTPClient,
    source: BinaryIO,
    destination: str,
    digest: str,
) -> None:
    """Write to an exclusive temporary file, then rename it into place.

    Args:
        sftp: Open SFTP session.
        source: Local file, positioned at its start.
        destination: Remote filename to publish.
        digest: SHA256 the transferred bytes must match.

    Raises:
        OSError: If the local file changed during the transfer.
        BaseException: Interruptions propagate after best-effort cleanup.
    """
    temporary = f"{destination}.{uuid4().hex}.tmp"
    created = False
    try:
        with sftp.open(temporary, "wx") as remote:
            created = True
            transferred = hashlib.sha256()
            for block in iter(lambda: source.read(_BLOCK_SIZE), b""):
                remote.write(block)
                transferred.update(block)
            if transferred.hexdigest() != digest:
                raise OSError(
                    "Local file changed during upload; nothing was published."
                )
        sftp.rename(temporary, destination)
    except BaseException:
        if created:
            try:
                sftp.remove(temporary)
            except OSError:
                pass  # Cleanup must not hide the original transfer failure.
        raise


def upload_sftp(
    file_path: str,
    url: str,
    *,
    known_hosts: str | None = None,
    accept_host_key: str | None = None,
    identity_file: str | None = None,
    password: str | None = None,
    passphrase: str | None = None,
    certificate: str | None = None,
    use_agent: bool = False,
    timeout: float = 15,
) -> UploadResult:
    """Atomically publish a file, refusing to replace different remote data.

    A matching remote SHA256 is a successful retry. New uploads use an
    exclusive temporary file in the same directory and a no-clobber SFTP
    rename. Authentication occurs only after host-key verification.

    The helpers' errors propagate unchanged: FileExistsError if different
    data already occupies the destination, OSError if local I/O or the
    transfer fails, paramiko.SSHException if host verification or
    authentication fails; interruptions propagate after cleanup.

    Args:
        file_path: Local file to deliver.
        url: Remote file URL, or a directory URL ending in a slash.
        known_hosts: Explicit known_hosts file; otherwise use standard files.
        accept_host_key: Independently verified OpenSSH SHA256 fingerprint.
        identity_file: Optional private key filename.
        password: Optional password supplied by the caller, never logged.
        passphrase: Optional private-key passphrase, never logged.
        certificate: Optional OpenSSH certificate for ``identity_file``.
        use_agent: Also offer ssh-agent keys with an identity or password.
        timeout: Network operation timeout in seconds.

    Returns:
        Destination, content hash and whether an earlier upload was reused.

    Raises:
        ValueError: If the URL, pin, filename, timeout or identity is invalid.
    """
    if timeout <= 0:
        raise ValueError("Timeout must be positive.")
    target, local, destination = _prepare(
        file_path, url, accept_host_key, timeout
    )
    credentials = Credentials(
        identity_file, certificate, password, passphrase, use_agent
    )
    trust = Trust(known_hosts, accept_host_key)
    with local.open("rb") as source:
        digest, size = _measure(source)
        with session(target, trust, credentials, timeout) as sftp:
            reused = _already_delivered(sftp, destination, digest, size)
            if not reused:
                _publish(sftp, source, destination, digest)
    return UploadResult(destination, digest, reused)


@contextmanager
def session(
    target: SFTPTarget,
    trust: Trust,
    credentials: Credentials,
    timeout: float,
) -> Iterator[paramiko.SFTPClient]:
    """Open the one audited SFTP connection upload and download share.

    The host-key policy is installed before ``connect``, so no credential
    leaves the machine until the server's key matches known_hosts or the
    explicit pin; the SFTP channel carries the same network timeout.

    Args:
        target: Validated host, port, username and path.
        trust: known_hosts file and optional SHA256 pin.
        credentials: Identity, password, passphrase and agent use.
        timeout: Network operation timeout in seconds.

    Yields:
        paramiko.SFTPClient: An open client, closed with its SSH
        connection on exit.
    """
    _validate_fingerprint(trust.accept_host_key)
    with paramiko.SSHClient() as client:
        _pin_host(client, trust.known_hosts, trust.accept_host_key)
        _connect(client, target, credentials, timeout)
        with _open_sftp(client, timeout) as sftp:
            yield sftp
