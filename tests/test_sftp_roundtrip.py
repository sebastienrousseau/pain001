# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Exercise uploads against a real, isolated localhost SSH/SFTP server."""

import os
import socket
import threading

import pytest

paramiko = pytest.importorskip("paramiko")

from pain001.transport.sftp import fingerprint, upload_sftp  # noqa: E402


class _Auth(paramiko.ServerInterface):
    """Authenticate only the test account over an encrypted connection."""

    def check_auth_password(self, username, password):
        """Validate the fixture's synthetic credentials."""
        return (
            paramiko.AUTH_SUCCESSFUL
            if (username, password) == ("ops", "test-only")
            else paramiko.AUTH_FAILED
        )

    def get_allowed_auths(self, username):
        """Advertise password authentication for this fixture."""
        return "password"

    def check_channel_request(self, kind, chanid):
        """Permit only SSH session channels."""
        return (
            paramiko.OPEN_SUCCEEDED
            if kind == "session"
            else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        )


class _Files(paramiko.SFTPServerInterface):
    """Map SFTP operations exclusively into the pytest temporary directory."""

    def __init__(self, server, *, root):
        """Record the isolated filesystem root."""
        super().__init__(server)
        self.root = root

    def _path(self, path):
        """Reject fixture requests that escape the isolated root."""
        result = (self.root / path.lstrip("/")).resolve()
        if not result.is_relative_to(self.root):
            raise PermissionError("Outside fixture root")
        return result

    def lstat(self, path):
        """Return real metadata or the appropriate SFTP error code."""
        try:
            return paramiko.SFTPAttributes.from_stat(self._path(path).lstat())
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def open(self, path, flags, attr):
        """Honor exclusive temporary creation and binary reads/writes."""
        try:
            descriptor = os.open(self._path(path), flags, 0o600)
            stream = os.fdopen(
                descriptor, "wb" if flags & os.O_WRONLY else "rb"
            )
            handle = paramiko.SFTPHandle(flags)
            if flags & os.O_WRONLY:
                handle.writefile = stream
            else:
                handle.readfile = stream
            return handle
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def rename(self, oldpath, newpath):
        """Publish atomically without replacing any existing destination."""
        try:
            os.link(self._path(oldpath), self._path(newpath))
            self._path(oldpath).unlink()
            return paramiko.SFTP_OK
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def remove(self, path):
        """Remove a failed upload's staging file."""
        try:
            self._path(path).unlink()
            return paramiko.SFTP_OK
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)


def test_real_sftp_upload_retry_and_changed_host(tmp_path):
    """A trusted host receives exact bytes; retries reuse them; bad pins fail."""
    root = tmp_path / "remote"
    (root / "inbox").mkdir(parents=True)
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    listener.settimeout(0.1)
    port = listener.getsockname()[1]
    stop = threading.Event()
    expected_disconnect = threading.Event()
    errors = []

    def serve():
        """Handle sequential client sessions until the test closes."""
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
            except (EOFError, ConnectionResetError) as exc:
                # Rejecting a host key intentionally closes the socket before
                # authentication. Paramiko may surface that as server EOF.
                if not expected_disconnect.is_set():
                    errors.append(exc)
            except Exception as exc:
                errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    local = tmp_path / "payments.xml"
    local.write_bytes(
        b'<?xml version="1.0"?><Document>synthetic test</Document>'
    )
    url = f"sftp://ops@127.0.0.1:{port}/inbox/"
    try:
        first = upload_sftp(
            str(local),
            url,
            password="test-only",
            accept_host_key=fingerprint(key),
            timeout=5,
        )
        assert not first.reused
        destination = root / "inbox" / "payments.xml"
        assert destination.read_bytes() == local.read_bytes()
        modified = destination.stat().st_mtime_ns
        second = upload_sftp(
            str(local),
            url,
            password="test-only",
            accept_host_key=fingerprint(key),
            timeout=5,
        )
        assert second.reused and second.sha256 == first.sha256
        assert destination.stat().st_mtime_ns == modified
        assert list((root / "inbox").glob("*.tmp")) == []
        expected_disconnect.set()
        with pytest.raises(paramiko.SSHException, match="Host key mismatch"):
            upload_sftp(
                str(local),
                url,
                password="test-only",
                accept_host_key="SHA256:" + "A" * 43,
                timeout=5,
            )
    finally:
        stop.set()
        thread.join(timeout=6)
        listener.close()
    assert not thread.is_alive()
    assert not errors
