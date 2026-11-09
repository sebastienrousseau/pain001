# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A real, isolated localhost SFTP server for download tests.

It serves one directory tree as the remote filesystem, authenticates
one synthetic account and supports what a download needs: listing,
stat, reading, removing and no-clobber renames. Nothing leaves
127.0.0.1.
"""

from __future__ import annotations

import os
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import paramiko

USER, PASSWORD = "ops", "test-only"


class _Auth(paramiko.ServerInterface):
    """Authenticate only the synthetic test account."""

    def check_auth_password(self, username: str, password: str) -> int:
        """Accept the fixture's credentials and nothing else."""
        ok = (username, password) == (USER, PASSWORD)
        return paramiko.AUTH_SUCCESSFUL if ok else paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        """Advertise password authentication only."""
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        """Permit SSH session channels only."""
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED


class _Files(paramiko.SFTPServerInterface):
    """Map SFTP operations into the fixture root, never outside it."""

    def __init__(self, server: object, *, root: Path) -> None:
        super().__init__(server)
        self.root = root

    def _path(self, path: str) -> Path:
        joined = Path(os.path.normpath(self.root / path.lstrip("/")))
        if not joined.is_relative_to(self.root):
            raise PermissionError("Outside fixture root")
        return joined

    def list_folder(self, path: str) -> list[paramiko.SFTPAttributes] | int:
        """List entries with lstat metadata, as OpenSSH does."""
        try:
            folder = self._path(path)
            out = []
            for name in sorted(os.listdir(folder)):
                attrs = paramiko.SFTPAttributes.from_stat(
                    (folder / name).lstat(), name
                )
                out.append(attrs)
            return out
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def stat(self, path: str) -> paramiko.SFTPAttributes | int:
        """Follow symlinks, as SSH_FXP_STAT does."""
        try:
            return paramiko.SFTPAttributes.from_stat(self._path(path).stat())
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def lstat(self, path: str) -> paramiko.SFTPAttributes | int:
        """Describe the entry itself, symlinks included."""
        try:
            return paramiko.SFTPAttributes.from_stat(self._path(path).lstat())
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def open(
        self, path: str, flags: int, attr: object
    ) -> paramiko.SFTPHandle | int:
        """Open for binary reading or exclusive writing."""
        try:
            descriptor = os.open(self._path(path), flags, 0o600)
            writing = bool(flags & os.O_WRONLY)
            stream = os.fdopen(descriptor, "wb" if writing else "rb")
            handle = paramiko.SFTPHandle(flags)
            if writing:
                handle.writefile = stream
            else:
                handle.readfile = stream
            return handle
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def rename(self, oldpath: str, newpath: str) -> int:
        """Rename without replacing an existing destination."""
        try:
            os.link(self._path(oldpath), self._path(newpath))
            self._path(oldpath).unlink()
            return paramiko.SFTP_OK
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def remove(self, path: str) -> int:
        """Remove one file."""
        try:
            self._path(path).unlink()
            return paramiko.SFTP_OK
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)


@dataclass(frozen=True)
class Server:
    """Where the fixture listens and the key it presents."""

    port: int
    key: paramiko.PKey
    root: Path

    def url(self, path: str) -> str:
        """An sftp:// URL for ``path`` on this server."""
        return f"sftp://{USER}@127.0.0.1:{self.port}{path}"


@contextmanager
def sftp_server(root: Path) -> Iterator[Server]:
    """Serve ``root`` over SFTP on an ephemeral localhost port."""
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    listener.settimeout(0.1)
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            try:
                with paramiko.Transport(connection) as transport:
                    transport.add_server_key(key)
                    transport.set_subsystem_handler(
                        "sftp", paramiko.SFTPServer, _Files, root=root
                    )
                    transport.start_server(server=_Auth())
                    while transport.is_active() and not stop.wait(0.01):
                        pass
            except (EOFError, ConnectionResetError, paramiko.SSHException):
                continue  # a refused host key closes the socket early

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield Server(listener.getsockname()[1], key, root)
    finally:
        stop.set()
        thread.join(timeout=6)
        listener.close()
