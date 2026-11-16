# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""SFTP upload contract: exact refusals, trust sources and timeouts.

The operator reads these messages at the command line, so each one is
pinned word for word; the connection arguments are pinned because a
lost timeout or trust file silently weakens the audited connection.
Every network object is a test double: nothing leaves the process.
"""

from __future__ import annotations

import errno
import hashlib
import io
import stat
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pain001.transport._algorithms import DISABLED_ALGORITHMS

# paramiko is the optional "upload" extra; skip, not fail, without it.
paramiko = pytest.importorskip("paramiko")
upload = pytest.importorskip("pain001.transport.sftp")


def _message(error: pytest.ExceptionInfo[BaseException]) -> str:
    """The raised exception's message."""
    return str(error.value)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (
            "https://ops@bank.example/in/",
            "Use sftp://user@host/absolute/path.",
        ),
        (
            "sftp://ops:pw@bank.example/in/",
            "SFTP URLs must not contain passwords, queries or fragments.",
        ),
        (
            "sftp://ops@bank.example/a/../b",
            "The remote path must be absolute and contain no traversal "
            "components.",
        ),
        (
            "sftp://ops@bank.example/in/%07",
            "SFTP coordinates must not contain control characters.",
        ),
        (
            "sftp://ops@bank.example:0/in/",
            "The SFTP port must be between 1 and 65535.",
        ),
    ],
)
def test_parse_target_refusals_are_worded_exactly(url, message):
    """Each refused URL names the rule it broke, verbatim."""
    with pytest.raises(ValueError) as error:
        upload.parse_target(url)
    assert _message(error) == message


@pytest.mark.parametrize(
    ("pin", "message", "chained"),
    [
        (
            "MD5:" + "A" * 46,
            "Use an OpenSSH SHA256 host-key fingerprint.",
            False,
        ),
        (
            "SHA256:" + "A" * 42,
            "Use an OpenSSH SHA256 host-key fingerprint.",
            False,
        ),
        ("SHA256:" + "*" * 43, "Invalid SHA256 host-key fingerprint.", True),
        (
            "SHA256:" + "A" * 42 + "B",
            "Invalid SHA256 host-key fingerprint.",
            False,
        ),
    ],
)
def test_fingerprint_refusals_are_worded_exactly(pin, message, chained):
    """Wrong shape, bad alphabet and non-canonical pins are told apart.

    A pin with characters outside base64 fails the strict decode, and
    that decoding error stays attached as the cause.
    """
    with pytest.raises(ValueError) as error:
        upload._validate_fingerprint(pin)
    assert _message(error) == message
    assert (error.value.__cause__ is not None) is chained


def test_host_key_policy_messages_are_exact():
    """The three host-key refusals tell the operator what to do next."""
    key = paramiko.RSAKey.generate(1024)
    other = paramiko.RSAKey.generate(1024)
    client = MagicMock()
    unknown = paramiko.HostKeys()
    with pytest.raises(paramiko.SSHException) as error:
        upload._PinnedHostPolicy(unknown, None).missing_host_key(
            client, "bank.example", key
        )
    assert _message(error) == (
        "Unknown host key; provision known_hosts or use --accept-host-key "
        "with an independently verified fingerprint."
    )
    with pytest.raises(paramiko.SSHException) as error:
        upload._PinnedHostPolicy(
            unknown, upload.fingerprint(other)
        ).missing_host_key(client, "bank.example", key)
    assert _message(error) == (
        "Host key mismatch with --accept-host-key; verify the fingerprint "
        "independently."
    )
    known = paramiko.HostKeys()
    known.add("bank.example", other.get_name(), other)
    with pytest.raises(paramiko.SSHException) as error:
        upload._PinnedHostPolicy(known, None).missing_host_key(
            client, "bank.example", key
        )
    assert _message(error) == (
        "Host key mismatch; verify the bank's key independently before "
        "updating known_hosts."
    )


def test_default_known_hosts_are_the_system_then_the_user_file(
    tmp_path, monkeypatch
):
    """Without --known-hosts, both OpenSSH trust files are read, in order."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    with patch.object(paramiko.HostKeys, "load") as load:
        upload._load_known_hosts(None)
    assert [call.args for call in load.call_args_list] == [
        ("/etc/ssh/ssh_known_hosts",),
        (str(tmp_path / ".ssh" / "known_hosts"),),
    ]


def test_host_fingerprint_probe_uses_the_target_and_timeout():
    """The probe dials the URL's host and port with the given timeout."""
    key = paramiko.RSAKey.generate(1024)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.get_remote_server_key.return_value = key
    with (
        patch.object(
            upload.socket, "create_connection", return_value=connection
        ) as dial,
        patch.object(paramiko, "Transport", return_value=transport) as make,
    ):
        assert upload.print_host_fingerprint(
            "sftp://ops@bank.example:2022/in/"
        ) == upload.fingerprint(key)
    dial.assert_called_once_with(("bank.example", 2022), timeout=15)
    make.assert_called_once_with(
        connection, disabled_algorithms=DISABLED_ALGORITHMS
    )
    transport.start_client.assert_called_once_with(timeout=15)


class _BoundedStream(io.BytesIO):
    """A stream that refuses unbounded reads, as a huge file would need."""

    def read(self, size: int | None = -1) -> bytes:
        """Return at most ``size`` bytes; refuse a read of everything."""
        if size is None or size < 0:
            raise AssertionError("unbounded read")
        return super().read(min(size, 3))


def test_hashing_reads_in_bounded_blocks():
    """A large local file is hashed without loading it whole."""
    data = b"0123456789"
    assert upload._digest(_BoundedStream(data)) == (
        hashlib.sha256(data).hexdigest()
    )


def _regular(size: int) -> Any:
    """Attributes of a regular remote file of ``size`` bytes."""
    attrs = paramiko.SFTPAttributes()
    attrs.st_mode, attrs.st_size = stat.S_IFREG, size
    return attrs


def test_remote_hash_of_a_file_served_in_small_chunks():
    """Matching bytes delivered in several reads still count as a match."""
    data = b"same-bytes"
    sftp = MagicMock()
    sftp.lstat.return_value = _regular(len(data))
    sftp.open.return_value = _BoundedStream(data)
    digest = hashlib.sha256(data).hexdigest()
    assert upload._remote_state(sftp, "/in/f.xml", digest, len(data)) is True
    sftp.open.assert_called_once_with("/in/f.xml", "rb")


@pytest.mark.parametrize(
    ("path", "name", "expected"),
    [
        ("/in/", "pay.xml", "/in/pay.xml"),
        ("/in/fixed.xml", "pay.xml", "/in/fixed.xml"),
        ("/in/", "my pay\x80.xml", "/in/my pay\x80.xml"),
    ],
)
def test_destination_names(path, name, expected):
    """A directory URL takes the local name; a file URL is used as given.

    Spaces and non-ASCII characters are ordinary filename characters.
    """
    target = upload.SFTPTarget("bank.example", 22, "ops", path)
    assert upload._destination(target, Path(name)) == expected


@pytest.mark.parametrize("name", ["bad\x1f.xml", "bad\x7f.xml"])
def test_destination_refuses_control_characters(name):
    """C0 controls and DEL in a local filename are refused, verbatim."""
    target = upload.SFTPTarget("bank.example", 22, "ops", "/in/")
    with pytest.raises(ValueError) as error:
        upload._destination(target, Path(name))
    assert _message(error) == (
        "The destination filename must not contain control characters."
    )


def test_pin_host_reads_the_named_known_hosts(tmp_path):
    """An explicit --known-hosts file is the trust the policy checks."""
    key = paramiko.RSAKey.generate(1024)
    trust = tmp_path / "known_hosts"
    trust.write_text(f"bank.example {key.get_name()} {key.get_base64()}\n")
    client = MagicMock()
    upload._pin_host(client, str(trust), None)
    policy = client.set_missing_host_key_policy.call_args.args[0]
    assert policy.known_hosts.check("bank.example", key)
    policy.missing_host_key(client, "bank.example", key)


@pytest.fixture
def wire(tmp_path):
    """A local source file and a fake SSH client with an empty remote."""
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
        ) as trust,
    ):
        yield local, client, sftp, trust


def test_upload_carries_the_timeout_and_trust_everywhere(wire):
    """One timeout bounds connect, banner, auth and the SFTP channel."""
    local, client, sftp, trust = wire
    upload.upload_sftp(
        str(local),
        "sftp://ops@bank.example:2022/in/",
        known_hosts="/srv/trust/known_hosts",
        password="test-password",
        timeout=0.5,
    )
    trust.assert_called_once_with("/srv/trust/known_hosts")
    call = client.connect.call_args
    assert call.args == ("bank.example",)
    assert call.kwargs["port"] == 2022
    assert call.kwargs["username"] == "ops"
    assert call.kwargs["password"] == "test-password"
    for name in ("timeout", "banner_timeout", "auth_timeout"):
        assert call.kwargs[name] == 0.5
    assert call.kwargs["disabled_algorithms"] == DISABLED_ALGORITHMS
    sftp.get_channel.return_value.settimeout.assert_called_once_with(0.5)


def test_upload_default_timeout_is_fifteen_seconds(wire):
    """Without --timeout, every network wait is bounded at 15 seconds."""
    local, client, sftp, _ = wire
    upload.upload_sftp(str(local), "sftp://ops@bank.example/in/")
    assert client.connect.call_args.kwargs["timeout"] == 15
    sftp.get_channel.return_value.settimeout.assert_called_once_with(15)


def test_upload_refuses_a_non_positive_timeout_verbatim(wire):
    """A zero timeout is refused before any connection, with its rule."""
    local, client, _, _ = wire
    with pytest.raises(ValueError) as error:
        upload.upload_sftp(
            str(local), "sftp://ops@bank.example/in/", timeout=0
        )
    assert _message(error) == "Timeout must be positive."
    client.connect.assert_not_called()


def test_a_bad_pin_is_refused_before_the_local_file_is_read(tmp_path):
    """Pin validation comes first, even when the local file is missing."""
    with pytest.raises(ValueError) as error:
        upload.upload_sftp(
            str(tmp_path / "missing.xml"),
            "sftp://ops@bank.example/in/",
            accept_host_key="MD5:abc",
        )
    assert _message(error) == "Use an OpenSSH SHA256 host-key fingerprint."


def test_a_missing_channel_is_reported_verbatim(wire):
    """No SFTP channel means no timeout could be set: refuse, exactly."""
    local, _, sftp, _ = wire
    sftp.get_channel.return_value = None
    with pytest.raises(paramiko.SSHException) as error:
        upload.upload_sftp(str(local), "sftp://ops@bank.example/in/")
    assert _message(error) == "SFTP session has no active channel."


def test_different_remote_bytes_are_refused_verbatim():
    """A collision names the remedy: choose a new filename."""
    sftp = MagicMock()
    sftp.lstat.return_value = _regular(3)
    sftp.open.return_value = io.BytesIO(b"abc")
    with pytest.raises(FileExistsError) as error:
        upload._already_delivered(sftp, "/in/f.xml", "0" * 64, 3)
    assert _message(error) == (
        "Remote destination already contains different data; choose a new "
        "filename."
    )


def test_publish_streams_in_bounded_blocks_and_renames():
    """The transfer reads the source in blocks and renames the temporary."""
    data = b"<Document>abcdef</Document>"
    sftp = MagicMock()
    remote = sftp.open.return_value.__enter__.return_value
    upload._publish(
        sftp,
        _BoundedStream(data),
        "/in/f.xml",
        hashlib.sha256(data).hexdigest(),
    )
    temporary = sftp.open.call_args.args[0]
    assert b"".join(c.args[0] for c in remote.write.call_args_list) == data
    sftp.rename.assert_called_once_with(temporary, "/in/f.xml")


def test_publish_removes_its_own_temporary_on_a_changed_source():
    """A changed source is refused verbatim and its temporary removed."""
    sftp = MagicMock()
    with pytest.raises(OSError) as error:
        upload._publish(sftp, io.BytesIO(b"new"), "/in/f.xml", "0" * 64)
    assert _message(error) == (
        "Local file changed during upload; nothing was published."
    )
    temporary = sftp.open.call_args.args[0]
    sftp.remove.assert_called_once_with(temporary)
    sftp.rename.assert_not_called()
