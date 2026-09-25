# SPDX-License-Identifier: Apache-2.0 OR MIT
"""SFTP trust, atomic publication, idempotence and failure cleanup."""

import errno
import hashlib
import io
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

paramiko = pytest.importorskip("paramiko")

from pain001.transport import sftp as upload  # noqa: E402


@pytest.fixture(scope="module")
def key():
    """An ephemeral SSH host key, never used outside tests."""
    return paramiko.RSAKey.generate(2048)


def test_parse_target():
    """URL decoding preserves a specified user, non-default port and path."""
    assert upload.parse_target(
        "sftp://ops@bank.example:2222/inbox/my%20file.xml"
    ) == upload.SFTPTarget("bank.example", 2222, "ops", "/inbox/my file.xml")
    assert upload.parse_target("sftp://ops@bank.example/inbox/").port == 22


@pytest.mark.parametrize(
    "url",
    [
        "https://ops@bank.example/inbox/",
        "sftp://bank.example/inbox/",
        "sftp://ops@/inbox/",
        "sftp://ops:secret@bank.example/inbox/",
        "sftp://ops@bank.example/inbox/?x=1",
        "sftp://ops@bank.example/inbox/#x",
        "sftp://ops@bank.example",
        "sftp://ops@bank.example/../file",
        "sftp://ops@bank.example/%2e/file",
        "sftp://ops@bank.example/inbox/%00",
        "sftp://ops%7f@bank.example/inbox/",
        "sftp://ops@bank.example:0/inbox/",
        "sftp://ops@bank.example:65536/inbox/",
    ],
)
def test_reject_unsafe_urls(url):
    """Credentials, control characters and traversal never reach SSH."""
    with pytest.raises(ValueError):
        upload.parse_target(url)


@pytest.mark.parametrize(
    "pin",
    [
        "MD5:abc",
        "SHA256:" + "*" * 43,
        "SHA256:" + "A" * 42 + "=",
        "SHA256:" + "A" * 42 + "B",
    ],
)
def test_invalid_fingerprints(pin):
    """Pins must use the canonical OpenSSH SHA256 encoding."""
    with pytest.raises(ValueError, match="fingerprint"):
        upload._validate_fingerprint(pin)


def test_host_key_policy(key):
    """Known keys and explicit pins are checked before authentication."""
    pin = upload.fingerprint(key)
    upload._validate_fingerprint(pin)
    upload._validate_fingerprint(None)
    client = MagicMock()
    known = paramiko.HostKeys()
    with pytest.raises(paramiko.SSHException, match="Unknown host key"):
        upload._PinnedHostPolicy(known, None).missing_host_key(
            client, "bank.example", key
        )
    upload._PinnedHostPolicy(known, pin).missing_host_key(
        client, "bank.example", key
    )
    assert (
        known.lookup("bank.example") is None
    )  # No automatic trust persistence.
    known.add("bank.example", key.get_name(), key)
    upload._PinnedHostPolicy(known, None).missing_host_key(
        client, "bank.example", key
    )
    upload._PinnedHostPolicy(known, pin).missing_host_key(
        client, "bank.example", key
    )
    wrong = "SHA256:" + "A" * 43
    with pytest.raises(paramiko.SSHException, match="mismatch"):
        upload._PinnedHostPolicy(known, wrong).missing_host_key(
            client, "bank.example", key
        )
    other = paramiko.RSAKey.generate(2048)
    with pytest.raises(paramiko.SSHException, match="mismatch"):
        upload._PinnedHostPolicy(
            known, upload.fingerprint(other)
        ).missing_host_key(client, "bank.example", other)


def test_load_known_hosts(tmp_path, key, monkeypatch):
    """Explicit trust files are read; missing default files are harmless."""
    trust = tmp_path / "known_hosts"
    trust.write_text(
        "bank.example " + key.get_name() + " " + key.get_base64() + "\n"
    )
    assert upload._load_known_hosts(str(trust)).check("bank.example", key)
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    assert len(upload._load_known_hosts(None)) == 0
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    with patch.object(paramiko.HostKeys, "load") as load:
        upload._load_known_hosts(None)
    assert load.call_count == 2


def test_host_key_inspection_does_not_authenticate(key):
    """Inspection only completes SSH key exchange and closes its resources."""
    connection = MagicMock()
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.get_remote_server_key.return_value = key
    with (
        patch.object(
            upload.socket, "create_connection", return_value=connection
        ),
        patch.object(paramiko, "Transport", return_value=transport),
    ):
        assert upload.print_host_fingerprint(
            "sftp://ops@bank.example/inbox/", 3
        ) == upload.fingerprint(key)
    transport.start_client.assert_called_once_with(timeout=3)
    transport.auth_password.assert_not_called()
    transport.__exit__.assert_called_once()
    connection.__exit__.assert_called_once()


def test_remote_missing_and_permission_failure():
    """Only ENOENT means absent; permission failures abort the upload."""
    sftp = MagicMock()
    sftp.lstat.side_effect = FileNotFoundError(errno.ENOENT, "absent")
    assert upload._remote_state(sftp, "/file", "digest", 4) is None
    sftp.lstat.side_effect = PermissionError(errno.EACCES, "denied")
    with pytest.raises(PermissionError):
        upload._remote_state(sftp, "/file", "digest", 4)


@pytest.mark.parametrize(
    "mode,size", [(None, 4), (stat.S_IFLNK, 4), (stat.S_IFREG, 5)]
)
def test_remote_metadata_mismatch(mode, size):
    """A symlink, nonregular object or different size is not a retry match."""
    sftp = MagicMock()
    sftp.lstat.return_value = paramiko.SFTPAttributes()
    sftp.lstat.return_value.st_mode = mode
    sftp.lstat.return_value.st_size = size
    assert upload._remote_state(sftp, "/file", "digest", 4) is False
    sftp.open.assert_not_called()


@pytest.mark.parametrize(
    "data,expected",
    [(b"same", True), (b"diff", False), (b"too-long", False), (b"a", False)],
)
def test_remote_hash_comparison(data, expected):
    """Equal size is insufficient, and a dishonest stream is bounded."""
    sftp = MagicMock()
    attrs = paramiko.SFTPAttributes()
    attrs.st_mode, attrs.st_size = stat.S_IFREG, 4
    sftp.lstat.return_value = attrs
    sftp.open.return_value = io.BytesIO(data)
    assert (
        upload._remote_state(
            sftp, "/file", hashlib.sha256(b"same").hexdigest(), 4
        )
        is expected
    )


@pytest.fixture
def connection(tmp_path):
    """A local source and observable SSH/SFTP connection lifecycle."""
    local = tmp_path / "payments.xml"
    local.write_bytes(b"<Document/>")
    client, sftp = MagicMock(), MagicMock()
    client.__enter__.return_value = client
    client.open_sftp.return_value = sftp
    sftp.__enter__.return_value = sftp
    sftp.lstat.side_effect = FileNotFoundError(errno.ENOENT, "absent")
    with (
        patch.object(paramiko, "SSHClient", return_value=client),
        patch.object(
            upload, "_load_known_hosts", return_value=paramiko.HostKeys()
        ),
    ):
        yield local, client, sftp


def test_atomic_upload(connection):
    """Data is written only to an exclusive temporary file, then renamed."""
    local, client, sftp = connection
    result = upload.upload_sftp(
        str(local),
        "sftp://ops@bank.example/inbox/",
        identity_file="keyfile",
        passphrase="test-passphrase",
    )
    assert result == upload.UploadResult(
        "/inbox/payments.xml",
        hashlib.sha256(local.read_bytes()).hexdigest(),
        False,
    )
    temporary = sftp.open.call_args.args[0]
    assert temporary.startswith("/inbox/payments.xml.") and temporary.endswith(
        ".tmp"
    )
    assert sftp.open.call_args.args[1] == "wx"
    remote = sftp.open.return_value.__enter__.return_value
    remote.write.assert_called_once_with(local.read_bytes())
    sftp.rename.assert_called_once_with(temporary, result.destination)
    assert client.connect.call_args.kwargs["allow_agent"] is False
    assert client.connect.call_args.kwargs["passphrase"] == "test-passphrase"
    sftp.remove.assert_not_called()
    client.__exit__.assert_called_once()


@pytest.mark.parametrize("same", [True, False])
def test_existing_destination(connection, same):
    """A retry skips the transfer; a collision never overwrites a payment."""
    local, client, sftp = connection
    with patch.object(upload, "_remote_state", return_value=same):
        if same:
            assert upload.upload_sftp(
                str(local),
                "sftp://ops@bank.example/payment.xml",
                password="test-password",
            ).reused
        else:
            with pytest.raises(FileExistsError, match="different data"):
                upload.upload_sftp(
                    str(local), "sftp://ops@bank.example/payment.xml"
                )
    sftp.open.assert_not_called()
    sftp.rename.assert_not_called()


@pytest.mark.parametrize("stage", ["create", "write", "rename", "cleanup"])
def test_failed_upload_cleanup(connection, stage):
    """Transfer failures leave no published partial file and preserve errors."""
    local, client, sftp = connection
    if stage == "create":
        sftp.open.side_effect = OSError("original failure")
    elif stage == "write":
        sftp.open.return_value.__enter__.return_value.write.side_effect = (
            OSError("original failure")
        )
    else:
        sftp.rename.side_effect = OSError("original failure")
        if stage == "cleanup":
            sftp.remove.side_effect = OSError("cleanup failure")
    with pytest.raises(OSError, match="original failure"):
        upload.upload_sftp(str(local), "sftp://ops@bank.example/inbox/")
    assert sftp.remove.call_count == (0 if stage == "create" else 1)
    client.__exit__.assert_called_once()


def test_local_file_change_aborts_before_publish(connection):
    """A source changed between hashing and transfer cannot be published."""
    local, client, sftp = connection
    original_open = sftp.open.return_value

    def change(*args):
        local.write_bytes(b"CHANGED")
        return original_open

    sftp.open.side_effect = change
    with pytest.raises(OSError, match="Local file changed"):
        upload.upload_sftp(str(local), "sftp://ops@bank.example/inbox/")
    sftp.rename.assert_not_called()
    sftp.remove.assert_called_once()


def test_invalid_timeout_and_filename(connection, tmp_path):
    """Invalid coordinates fail before making a network connection."""
    local, client, sftp = connection
    with pytest.raises(ValueError, match="positive"):
        upload.upload_sftp(
            str(local), "sftp://ops@bank.example/inbox/", timeout=0
        )
    with pytest.raises(ValueError, match="control"):
        upload.upload_sftp(
            str(tmp_path / "bad\n.xml"), "sftp://ops@bank.example/inbox/"
        )
    client.connect.assert_not_called()


def test_missing_sftp_channel(connection):
    """A failed SFTP channel cannot start a transfer without timeouts."""
    local, client, sftp = connection
    sftp.get_channel.return_value = None
    with pytest.raises(paramiko.SSHException, match="active channel"):
        upload.upload_sftp(str(local), "sftp://ops@bank.example/inbox/")
    sftp.open.assert_not_called()
