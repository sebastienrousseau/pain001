# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Downloads: exactly-once ledger, dispositions, caps and name safety."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

paramiko = pytest.importorskip("paramiko")

from pain001.transport import download  # noqa: E402
from pain001.transport.download import (  # noqa: E402
    DownloadPolicy,
    download_sftp,
    parse_after_fetch,
)
from pain001.transport.ledger import Entry, Ledger  # noqa: E402
from pain001.transport.sftp import fingerprint  # noqa: E402
from tests.sftp_fixture import PASSWORD, sftp_server  # noqa: E402

REPLY = b'<?xml version="1.0"?><Document>synthetic reply</Document>'


@pytest.fixture
def bank(tmp_path: Path):
    """A remote outbox with two replies and a local inbox."""
    root = tmp_path / "remote"
    (root / "outbox").mkdir(parents=True)
    (root / "archive").mkdir()
    (root / "outbox" / "a.xml").write_bytes(REPLY)
    (root / "outbox" / "b.xml").write_bytes(REPLY + b" ")
    local = tmp_path / "local"
    local.mkdir()
    with sftp_server(root) as server:
        yield server, local


def _get(server, local, policy=None, **extra):
    return download_sftp(
        server.url("/outbox/"),
        str(local),
        policy=policy or DownloadPolicy(),
        password=PASSWORD,
        accept_host_key=fingerprint(server.key),
        timeout=5,
        **extra,
    )


def test_keep_saves_each_file_once(bank):
    """A second run skips files the ledger knows; nothing is rewritten."""
    server, local = bank
    first = _get(server, local)
    assert sorted(f.status for f in first.files) == ["saved", "saved"]
    assert (local / "a.xml").read_bytes() == REPLY
    assert stat.S_IMODE((local / "a.xml").stat().st_mode) == 0o600
    ledger = local / ".pain001-ledger.sqlite3"
    assert stat.S_IMODE(ledger.stat().st_mode) == 0o600
    second = _get(server, local)
    assert [f.status for f in second.files] == ["known", "known"]
    assert sorted(p.name for p in local.iterdir()) == [
        ".pain001-ledger.sqlite3",
        "a.xml",
        "b.xml",
    ]
    assert (server.root / "outbox" / "a.xml").exists()


def test_delete_removes_the_remote_only_after_saving(bank):
    server, local = bank
    result = _get(server, local, DownloadPolicy(after_fetch="delete"))
    assert [f.status for f in result.files] == ["saved", "saved"]
    assert list((server.root / "outbox").iterdir()) == []
    assert (local / "b.xml").read_bytes() == REPLY + b" "


def test_move_archives_the_remote(bank):
    server, local = bank
    _get(server, local, DownloadPolicy(after_fetch="move:/archive"))
    assert sorted(p.name for p in (server.root / "archive").iterdir()) == [
        "a.xml",
        "b.xml",
    ]
    assert list((server.root / "outbox").iterdir()) == []


def test_new_content_under_a_known_name_is_kept_beside_it(bank):
    """A reappearing name with new bytes never overwrites the first."""
    server, local = bank
    _get(server, local, DownloadPolicy(after_fetch="delete"))
    changed = REPLY.replace(b"synthetic", b"second")
    (server.root / "outbox" / "a.xml").write_bytes(changed)
    result = _get(server, local, DownloadPolicy(after_fetch="delete"))
    sha8 = hashlib.sha256(changed).hexdigest()[:8]
    assert [f.local for f in result.files] == [str(local / f"a.{sha8}.xml")]
    assert (local / "a.xml").read_bytes() == REPLY
    assert (local / f"a.{sha8}.xml").read_bytes() == changed


def test_same_content_reappearing_is_known_and_disposed(bank):
    server, local = bank
    _get(server, local, DownloadPolicy(after_fetch="delete"))
    (server.root / "outbox" / "a.xml").write_bytes(REPLY)
    result = _get(server, local, DownloadPolicy(after_fetch="delete"))
    assert [f.status for f in result.files] == ["known"]
    assert not (server.root / "outbox" / "a.xml").exists()


def test_a_crash_before_disposal_is_finished_next_run(bank, monkeypatch):
    """Saved and recorded, then interrupted: the retry only disposes."""
    server, local = bank

    def boom(*args, **kwargs):
        raise OSError("connection lost")

    monkeypatch.setattr(download, "_dispose", boom)
    with pytest.raises(OSError, match="connection lost"):
        _get(server, local, DownloadPolicy(after_fetch="delete"))
    monkeypatch.undo()
    assert (local / "a.xml").exists()
    result = _get(server, local, DownloadPolicy(after_fetch="delete"))
    assert [f.status for f in result.files] == ["known", "saved"]
    assert list((server.root / "outbox").iterdir()) == []


def test_pattern_hidden_temporary_and_symlinks_are_skipped(bank):
    server, local = bank
    outbox = server.root / "outbox"
    (outbox / "c.txt").write_bytes(b"x")
    (outbox / ".hidden.xml").write_bytes(b"x")
    (outbox / "d.xml.0a1b.tmp").write_bytes(b"x")
    os.symlink("/etc/hosts", outbox / "link.xml")
    result = _get(server, local, DownloadPolicy(pattern="*.xml"))
    assert sorted(Path(f.remote).name for f in result.files) == [
        "a.xml",
        "b.xml",
    ]
    assert "link.xml" in result.skipped


def test_caps_stop_at_the_file_and_byte_budget(bank):
    server, local = bank
    result = _get(server, local, DownloadPolicy(max_files=1))
    assert len(result.files) == 1 and result.remaining == 1
    result = _get(server, local, DownloadPolicy(max_bytes=len(REPLY)))
    assert result.remaining == 1
    assert [f.status for f in result.files] == ["known"]


def test_settle_skips_files_still_changing(bank):
    server, local = bank

    def grow(seconds: float) -> None:
        with (server.root / "outbox" / "b.xml").open("ab") as stream:
            stream.write(b"more")

    result = _get(server, local, DownloadPolicy(settle_seconds=1), sleep=grow)
    assert [Path(f.remote).name for f in result.files] == ["a.xml"]
    assert "b.xml" in result.skipped


def test_a_file_that_grows_during_transfer_is_refused(bank, monkeypatch):
    server, local = bank
    listed = download._list

    def shrink(*args):
        files, skipped = listed(*args)
        return [
            (name, size - 1, mtime) for name, size, mtime in files
        ], skipped

    monkeypatch.setattr(download, "_list", shrink)
    with pytest.raises(OSError, match="changed size"):
        _get(server, local)
    assert [p.name for p in local.iterdir() if p.suffix == ".part"] == []


def test_an_unknown_host_key_sends_no_credentials(bank):
    server, local = bank
    with pytest.raises(paramiko.SSHException, match="Host key mismatch"):
        download_sftp(
            server.url("/outbox/"),
            str(local),
            password=PASSWORD,
            accept_host_key="SHA256:" + "A" * 43,
            timeout=5,
        )


@pytest.mark.parametrize(
    "value, expected",
    [
        ("keep", ("keep", None)),
        ("delete", ("delete", None)),
        ("move:/archive", ("move", "/archive")),
        ("move:/archive/", ("move", "/archive")),
    ],
)
def test_parse_after_fetch(value, expected):
    assert parse_after_fetch(value) == expected


@pytest.mark.parametrize(
    "value", ["", "copy", "move:", "move:archive", "move:/a/../b", "move:/a\n"]
)
def test_parse_after_fetch_refuses(value):
    with pytest.raises(ValueError):
        parse_after_fetch(value)


@pytest.mark.parametrize(
    "url", ["sftp://ops@h/outbox", "sftp://ops@h/outbox/a.xml"]
)
def test_the_remote_must_be_a_directory(tmp_path, url):
    with pytest.raises(ValueError, match="directory"):
        download_sftp(url, str(tmp_path))


def test_the_local_directory_must_exist_and_not_be_a_link(tmp_path):
    os.symlink(tmp_path, tmp_path / "link")
    for target in (tmp_path / "missing", tmp_path / "link"):
        with pytest.raises(ValueError, match="directory"):
            download_sftp("sftp://ops@h/outbox/", str(target))


@pytest.mark.parametrize(
    "policy",
    [
        DownloadPolicy(max_files=0),
        DownloadPolicy(max_bytes=0),
        DownloadPolicy(settle_seconds=-1),
    ],
)
def test_policy_bounds(tmp_path, policy):
    with pytest.raises(ValueError):
        download_sftp("sftp://ops@h/outbox/", str(tmp_path), policy=policy)


def test_ledger_refuses_a_symlink_and_tightens_permissions(tmp_path):
    target = tmp_path / "real.sqlite3"
    os.symlink(target, tmp_path / "link.sqlite3")
    with pytest.raises(ValueError, match="symlink"):
        Ledger(tmp_path / "link.sqlite3")
    # Report a legacy group-readable mode without exposing a real file.
    # The actual fixture and the ledger must remain private throughout.
    loose = tmp_path / "loose.sqlite3"
    loose.touch(mode=0o600)
    real_lstat = Path.lstat

    def legacy_mode(path):
        details = real_lstat(path)
        if path == loose:
            return os.stat_result((stat.S_IFREG | 0o640, *details[1:]))
        return details

    with (
        patch.object(Path, "lstat", autospec=True, side_effect=legacy_mode),
        patch("pain001.transport.ledger.os.chmod", wraps=os.chmod) as harden,
    ):
        Ledger(loose).close()
        harden.assert_called_once_with(loose, 0o600)
    assert stat.S_IMODE(loose.stat().st_mode) == 0o600


def test_ledger_round_trip(tmp_path):
    with Ledger(tmp_path / "l.sqlite3") as ledger:
        entry = Entry("ops@h:22/o/a.xml", "ab" * 32, 3, 7, "/x/a.xml")
        assert ledger.find(entry.source, entry.sha256) is None
        ledger.record(entry)
        assert ledger.find(entry.source, entry.sha256) == entry
        assert ledger.known(entry.source, 3, 7) == entry
        assert ledger.known(entry.source, 4, 7) is None
        ledger.mark_disposed(entry)
        assert ledger.find(entry.source, entry.sha256).disposed


def test_an_identical_local_file_without_a_ledger_row_is_known(bank):
    server, local = bank
    (local / "a.xml").write_bytes(REPLY)
    result = _get(server, local, DownloadPolicy(pattern="a.xml"))
    assert [f.status for f in result.files] == ["known"]
    assert [p.name for p in local.glob("a.*")] == ["a.xml"]


def test_both_names_taken_by_other_bytes_is_refused(bank):
    server, local = bank
    sha8 = hashlib.sha256(REPLY).hexdigest()[:8]
    (local / "a.xml").write_bytes(b"other")
    (local / f"a.{sha8}.xml").write_bytes(b"other too")
    with pytest.raises(FileExistsError, match=sha8):
        _get(server, local, DownloadPolicy(pattern="a.xml"))
    assert [p for p in local.iterdir() if p.suffix == ".part"] == []


def test_same_bytes_with_a_new_mtime_are_known(bank):
    """Attributes changed, content did not: read, matched, not saved."""
    server, local = bank
    _get(server, local, DownloadPolicy(pattern="a.xml"))
    os.utime(server.root / "outbox" / "a.xml", (1, 1))
    result = _get(server, local, DownloadPolicy(pattern="a.xml"))
    assert [f.status for f in result.files] == ["known"]
    assert [p.name for p in local.glob("a.*")] == ["a.xml"]


def test_the_ledger_must_be_a_regular_file(tmp_path):
    with pytest.raises(ValueError, match="regular file"):
        Ledger(tmp_path)


def test_credentials_never_show_secrets():
    from pain001.transport.sftp import Credentials

    shown = repr(Credentials(password="hunter2", passphrase="p"))
    assert "hunter2" not in shown and "'p'" not in shown


ACCP = b'<?xml version="1.0"?><Document>STATUS ACCP</Document>'
RJCT = b'<?xml version="1.0"?><Document>STATUS RJCT</Document>'


@pytest.mark.parametrize("after", ["delete", "move:/archive"])
def test_a_reissued_reply_of_the_same_size_is_read_before_disposal(
    bank, after
):
    """Same name, size and mtime, new bytes: saved, never dropped unread."""
    server, local = bank
    status = server.root / "outbox" / "STATUS.xml"
    status.write_bytes(ACCP)
    os.utime(status, (1_700_000_000, 1_700_000_000))
    policy = DownloadPolicy(pattern="STATUS.xml", after_fetch=after)
    _get(server, local, policy)
    for archived in (server.root / "archive").iterdir():
        archived.unlink()
    status.write_bytes(RJCT)
    os.utime(status, (1_700_000_000, 1_700_000_000))
    result = _get(server, local, policy)
    sha8 = hashlib.sha256(RJCT).hexdigest()[:8]
    assert [f.status for f in result.files] == ["saved"]
    assert (local / f"STATUS.{sha8}.xml").read_bytes() == RJCT
    assert (local / "STATUS.xml").read_bytes() == ACCP
    assert not status.exists()


def test_a_server_without_mtimes_never_matches_the_ledger(bank, monkeypatch):
    """No mtime is no evidence: a keep run reads the file again."""
    server, local = bank
    listed = download._list

    def no_mtime(*args):
        files, skipped = listed(*args)
        return [(name, size, 0) for name, size, _ in files], skipped

    monkeypatch.setattr(download, "_list", no_mtime)
    status = server.root / "outbox" / "STATUS.xml"
    status.write_bytes(ACCP)
    policy = DownloadPolicy(pattern="STATUS.xml")
    _get(server, local, policy)
    status.write_bytes(RJCT)
    result = _get(server, local, policy)
    sha8 = hashlib.sha256(RJCT).hexdigest()[:8]
    assert [f.status for f in result.files] == ["saved"]
    assert (local / f"STATUS.{sha8}.xml").read_bytes() == RJCT


@pytest.mark.parametrize(
    "name", ["C:x.xml", "a\x9b2J.xml", "a\x85.xml", "a\x1b.xml", "a:b.xml"]
)
def test_c1_controls_and_colons_are_unsafe_names(name):
    """C1 controls reach terminals; a colon escapes --to on Windows."""
    assert not download._safe_name(name)


def test_c1_controls_are_refused_in_the_archive_path():
    with pytest.raises(ValueError):
        parse_after_fetch("move:/archive\x9b")
