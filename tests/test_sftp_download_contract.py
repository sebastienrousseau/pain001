# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Download contract: names, budgets, the ledger shortcut and wiring.

The SFTP side is a test double that serves bytes from memory, so each
rule is checked on its own: which names are safe, how the byte budget
and file cap count, when a ``keep`` run trusts the ledger instead of
reading a file again, and what reaches the audited connection.
"""

from __future__ import annotations

import hashlib
import io
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from pain001.transport.ledger import Entry, Ledger

# paramiko is the optional "upload" extra; skip, not fail, without it.
paramiko = pytest.importorskip("paramiko")
download = pytest.importorskip("pain001.transport.download")
DownloadPolicy = download.DownloadPolicy
SFTPTarget = pytest.importorskip("pain001.transport.sftp").SFTPTarget

TARGET = SFTPTarget("bank.example", 22, "ops", "/outbox/")


class _Chunked(io.BytesIO):
    """A remote stream that serves a few bytes per read, never all."""

    def read(self, size: int | None = -1) -> bytes:
        """Return at most three bytes; refuse an unbounded read."""
        if size is None or size < 0:
            raise AssertionError("unbounded read")
        return super().read(min(size, 3))


def _attrs(name: str, size: int | None, mtime: int | None) -> Any:
    """Listing attributes for a regular remote file."""
    attrs = paramiko.SFTPAttributes()
    attrs.filename, attrs.st_mode = name, stat.S_IFREG
    attrs.st_size, attrs.st_mtime = size, mtime
    return attrs


def _run(tmp_path: Path, files: dict[str, bytes], **extra: Any) -> Any:
    """A run over an in-memory outbox, a real ledger and a local dir."""
    local = tmp_path / "inbox"
    local.mkdir(exist_ok=True)
    sftp = MagicMock()
    sftp.open.side_effect = lambda path, mode="r": _Chunked(
        files[path.rsplit("/", 1)[1]]
    )
    sftp.listdir_attr.return_value = [
        _attrs(name, len(data), 1_700_000_000) for name, data in files.items()
    ]
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    disposal = extra.pop("disposal", ("keep", None))
    budget = extra.pop("budget", 1_000)
    return download._Run(sftp, TARGET, local, ledger, disposal, budget)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("move:/arcX/", ("move", "/arcX")),
        ("move:/archive//", ("move", "/archive")),
    ],
)
def test_move_directory_keeps_its_name_and_drops_trailing_slashes(
    value, expected
):
    """Only slashes are trimmed from the archive directory."""
    assert download.parse_after_fetch(value) == expected


@pytest.mark.parametrize(
    "value", ["move:/a/./b", "move:/a/../b", "archive", "move:relative"]
)
def test_after_fetch_refusal_is_worded_exactly(value):
    """Dot segments, relative paths and unknown actions get one message."""
    with pytest.raises(ValueError) as error:
        download.parse_after_fetch(value)
    assert str(error.value) == (
        "--after-fetch must be keep, delete or move:/absolute/dir."
    )


@pytest.mark.parametrize(
    ("text", "printable"),
    [
        (" ", True),
        ("~", True),
        ("\xa0", True),
        ("\x1f", False),
        ("\x7f", False),
        ("\x80", False),
        ("\x9f", False),
    ],
)
def test_printable_bounds(text, printable):
    """Space and NBSP are printable; C0, DEL and C1 controls are not."""
    assert download._printable(text) is printable


@pytest.mark.parametrize(
    ("name", "safe"),
    [
        ("my reply.xml", True),
        ("a/b.xml", False),
        ("a\\b.xml", False),
        ("a.xml.tmp", False),
        ("a.xml.TMP", True),
        ("a.xml.part", False),
        ("a.xml.PART", True),
    ],
)
def test_safe_name_rules(name, safe):
    """Path separators and lower-case temporary suffixes are refused."""
    assert download._safe_name(name) is safe


def test_listing_defaults_missing_size_and_mtime_to_zero():
    """A server that omits size or mtime is listed as 0 for each."""
    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        _attrs("a.xml", None, None),
        _attrs("b.xml", 5, 1_700_000_123),
    ]
    files, skipped = download._list(sftp, "/outbox/", "*")
    assert files == [("a.xml", 0, 0), ("b.xml", 5, 1_700_000_123)]
    assert skipped == []


def test_settle_does_not_wait_when_zero_and_waits_the_time_given(tmp_path):
    """No settle time means no sleep; otherwise sleep exactly that long."""
    run = _run(tmp_path, {"a.xml": b"abc"})
    listed = [("a.xml", 3, 1_700_000_000)]
    sleep = MagicMock()
    assert download._settled(run, listed, "*", (0, sleep)) == (listed, [])
    sleep.assert_not_called()
    assert download._settled(run, listed, "*", (2.5, sleep)) == (listed, [])
    sleep.assert_called_once_with(2.5)
    run.ledger.close()


def test_receive_writes_a_hidden_part_file_in_the_target_dir(tmp_path):
    """The temporary is ``.pain001-*.part`` beside the final file."""
    data = b"<Document>reply</Document>"
    run = _run(tmp_path, {"a.xml": data})
    seen: list[list[str]] = []

    def observe(path: str, mode: str = "r") -> io.BytesIO:
        seen.append(sorted(p.name for p in run.local.iterdir()))
        return _Chunked(data)

    run.sftp.open.side_effect = observe
    path, digest = download._receive(run, "a.xml", len(data))
    run.sftp.open.assert_called_once_with("/outbox/a.xml", "rb")
    assert path.parent == run.local
    assert path.name.startswith(".pain001-") and path.name.endswith(".part")
    assert seen == [[path.name]]
    assert path.read_bytes() == data
    assert digest == hashlib.sha256(data).hexdigest()
    run.ledger.close()


def test_receive_cleanup_tolerates_a_vanished_temporary(tmp_path):
    """The original error surfaces even if the temporary is already gone."""
    run = _run(tmp_path, {})

    def vanish(path: str, mode: str = "r") -> io.BytesIO:
        for leftover in run.local.glob(".pain001-*.part"):
            leftover.unlink()
        raise OSError("connection lost")

    run.sftp.open.side_effect = vanish
    with pytest.raises(OSError, match="^connection lost$"):
        download._receive(run, "a.xml", 3)
    run.ledger.close()


def test_file_hash_reads_in_bounded_blocks(tmp_path, monkeypatch):
    """A local file is hashed block by block, never read whole."""
    data = b"0123456789"
    target = tmp_path / "f.xml"
    target.write_bytes(data)
    monkeypatch.setattr(Path, "open", lambda self, *a, **k: _Chunked(data))
    assert download._file_sha256(target) == hashlib.sha256(data).hexdigest()


def test_place_refusal_names_the_eight_character_variant(tmp_path):
    """Both names taken by other bytes: the message names the sha8."""
    sha = hashlib.sha256(b"new").hexdigest()
    (tmp_path / "a.xml").write_bytes(b"one")
    (tmp_path / f"a.{sha[:8]}.xml").write_bytes(b"two")
    received = tmp_path / ".pain001-x.part"
    received.write_bytes(b"new")
    with pytest.raises(FileExistsError) as error:
        download._place(received, tmp_path, "a.xml", sha)
    assert str(error.value) == (
        f"a.xml and its {sha[:8]} variant already hold other bytes."
    )
    assert not received.exists()


def _remember(run: Any, name: str, data: bytes, mtime: int) -> Entry:
    """Record ``name`` in the ledger as an earlier run would have."""
    entry = Entry(
        run.source(name),
        hashlib.sha256(data).hexdigest(),
        len(data),
        mtime,
        str(run.local / name),
    )
    run.ledger.record(entry)
    return entry


def test_keep_run_trusts_the_ledger_for_an_unchanged_listing(tmp_path):
    """Same size and a positive mtime: the row is reused, nothing read."""
    run = _run(tmp_path, {"a.xml": b"abc"})
    entry = _remember(run, "a.xml", b"abc", 1)
    assert download._unchanged(run, run.source("a.xml"), 3, 1) == entry
    assert download._fetch(run, ("a.xml", 3, 1)) is True
    run.sftp.open.assert_not_called()
    assert run.files == [
        download.Fetched(
            "/outbox/a.xml", entry.local_path, entry.sha256, 3, "known"
        )
    ]
    run.ledger.close()


def test_a_delete_run_never_trusts_the_listing(tmp_path):
    """Deleting needs the bytes read first, even with a matching row."""
    run = _run(tmp_path, {"a.xml": b"abc"}, disposal=("delete", None))
    _remember(run, "a.xml", b"abc", 1)
    assert download._unchanged(run, run.source("a.xml"), 3, 1) is None
    run.ledger.close()


def test_saved_file_is_reported_with_its_hash_and_size(tmp_path):
    """A new file is saved and reported with what was read."""
    data = b"<Document>new</Document>"
    run = _run(tmp_path, {"a.xml": data})
    assert download._fetch(run, ("a.xml", len(data), 7)) is True
    assert run.files == [
        download.Fetched(
            "/outbox/a.xml",
            str(run.local / "a.xml"),
            hashlib.sha256(data).hexdigest(),
            len(data),
            "saved",
        )
    ]
    run.ledger.close()


def test_budget_admits_an_exact_fit_and_is_spent(tmp_path):
    """A file the size of the budget fits; the next one no longer does."""
    run = _run(tmp_path, {"a.xml": b"abcd", "b.xml": b"e"}, budget=4)
    assert download._fetch(run, ("a.xml", 4, 1)) is True
    assert run.budget == 0
    assert download._fetch(run, ("b.xml", 1, 1)) is False
    assert [Path(f.remote).name for f in run.files] == ["a.xml"]
    run.ledger.close()


def test_file_cap_reports_what_remains(tmp_path):
    """Three files and a cap of two: two handled, one left for later."""
    files = {"a.xml": b"a", "b.xml": b"b", "c.xml": b"c"}
    run = _run(tmp_path, files)
    result = download._fetch_all(run, DownloadPolicy(max_files=2), MagicMock())
    assert [Path(f.remote).name for f in result.files] == ["a.xml", "b.xml"]
    assert result.remaining == 1
    run.ledger.close()


@pytest.mark.parametrize(
    ("url", "policy", "message"),
    [
        (
            "sftp://ops@bank.example/outbox/a.xml",
            DownloadPolicy(),
            "Download from a directory URL ending in '/'.",
        ),
        (
            "sftp://ops@bank.example/outbox/",
            DownloadPolicy(max_bytes=0),
            "max_files and max_bytes must be at least 1.",
        ),
        (
            "sftp://ops@bank.example/outbox/",
            DownloadPolicy(settle_seconds=-1),
            "settle_seconds must not be negative.",
        ),
    ],
)
def test_input_refusals_are_worded_exactly(tmp_path, url, policy, message):
    """Bad coordinates and limits are refused offline, verbatim."""
    with pytest.raises(ValueError) as error:
        download.download_sftp(url, str(tmp_path), policy=policy)
    assert str(error.value) == message


def test_a_one_byte_budget_is_allowed(tmp_path):
    """The smallest budget the docs allow is accepted."""
    target = download.parse_target("sftp://ops@bank.example/outbox/")
    assert download._check_inputs(
        target, tmp_path, DownloadPolicy(max_bytes=1)
    ) == ("keep", None)


@pytest.fixture
def opened(monkeypatch):
    """Replace the audited session; record what it was asked to open."""
    calls: list[tuple[Any, ...]] = []

    @contextmanager
    def session(*args: Any) -> Iterator[Any]:
        calls.append(args)
        sftp = MagicMock()
        sftp.listdir_attr.return_value = []
        yield sftp

    monkeypatch.setattr(download, "session", session)
    return calls


def test_download_defaults_reach_the_session(tmp_path, opened):
    """No agent, a 15 second timeout and the ledger inside ``--to``."""
    download.download_sftp("sftp://ops@bank.example/outbox/", str(tmp_path))
    (target, trust, credentials, timeout) = opened[0]
    assert target == TARGET
    assert credentials == download.Credentials()
    assert credentials.use_agent is False
    assert trust == download.Trust()
    assert timeout == 15
    assert (tmp_path / download.LEDGER_NAME).is_file()


def test_download_options_reach_the_session(tmp_path, opened):
    """Every trust and credential option is handed on unchanged."""
    ledger = tmp_path / "elsewhere.sqlite3"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    download.download_sftp(
        "sftp://ops@bank.example/outbox/",
        str(inbox),
        ledger_path=str(ledger),
        known_hosts="/srv/known_hosts",
        identity_file="/keys/id_ed25519",
        certificate="/keys/id_ed25519-cert.pub",
        password="test-password",
        passphrase="test-passphrase",
        use_agent=True,
        timeout=3,
    )
    (_, trust, credentials, timeout) = opened[0]
    assert trust == download.Trust("/srv/known_hosts", None)
    assert credentials == download.Credentials(
        "/keys/id_ed25519",
        "/keys/id_ed25519-cert.pub",
        "test-password",
        "test-passphrase",
        True,
    )
    assert timeout == 3
    assert ledger.is_file()
    assert not (inbox / download.LEDGER_NAME).exists()
