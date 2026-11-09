# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Local SQLite record of every file a download has saved.

The ledger is what makes a download exactly-once: a file is saved
locally, then its row is committed, and only then is the remote copy
deleted or moved. A run interrupted between those steps finds the row
next time and finishes the disposal without saving the file again.
The database is created 0600 and never follows a symlink.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fetched (
    source TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime INTEGER NOT NULL,
    local_path TEXT NOT NULL,
    disposed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, sha256)
)
"""
_SELECT_BY_CONTENT = (
    "SELECT source, sha256, size, mtime, local_path, disposed FROM fetched "
    "WHERE source = ? AND sha256 = ?"
)
_SELECT_BY_ATTRIBUTES = (
    "SELECT source, sha256, size, mtime, local_path, disposed FROM fetched "
    "WHERE source = ? AND size = ? AND mtime = ?"
)
_INSERT = (
    "INSERT INTO fetched (source, sha256, size, mtime, local_path, disposed) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)
_DISPOSED = "UPDATE fetched SET disposed = 1 WHERE source = ? AND sha256 = ?"


@dataclass(frozen=True)
class Entry:
    """One saved file: where it came from, its content and where it went.

    ``source`` is ``user@host:port/remote/path``; ``size`` and ``mtime``
    are the remote attributes the file was listed with.
    """

    source: str
    sha256: str
    size: int
    mtime: int
    local_path: str
    disposed: bool = False


def _create_private(path: Path) -> None:
    """Create the database file 0600, refusing a symlink in its place."""
    if path.is_symlink():
        raise ValueError(f"Refusing a symlink as the ledger: {path}")
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    except FileExistsError:
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError(
                f"The ledger is not a regular file: {path}"
            ) from None
        if stat.S_IMODE(mode) & 0o077:
            os.chmod(path, 0o600)


class Ledger:
    """Exactly-once record of saved files, one row per source and content."""

    def __init__(self, path: Path) -> None:
        _create_private(path)
        self._db = sqlite3.connect(path, isolation_level=None)
        self._db.execute(_SCHEMA)

    def __enter__(self) -> Ledger:
        """Use the ledger as a context manager that closes it on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the database, whether or not the block raised."""
        self.close()

    def close(self) -> None:
        """Close the database connection."""
        self._db.close()

    def _one(self, query: str, *args: object) -> Entry | None:
        """Run one of the fixed SELECTs and return its row as an Entry."""
        row = self._db.execute(query, args).fetchone()
        if row is None:
            return None
        source, sha256, size, mtime, local_path, disposed = row
        return Entry(source, sha256, size, mtime, local_path, bool(disposed))

    def find(self, source: str, sha256: str) -> Entry | None:
        """Return the row for this source and content, if saved before.

        Args:
            source: ``user@host:port/remote/path``.
            sha256: Hex SHA256 of the file's bytes.

        Returns:
            The saved entry, or None.
        """
        return self._one(_SELECT_BY_CONTENT, source, sha256)

    def known(self, source: str, size: int, mtime: int) -> Entry | None:
        """Return a row whose remote size and mtime match, if any.

        It lets a ``keep`` download skip files it already holds without
        reading them again; a file whose size or mtime changed is read
        and hashed.

        Args:
            source: ``user@host:port/remote/path``.
            size: Listed remote size in bytes.
            mtime: Listed remote modification time in seconds.

        Returns:
            The matching entry, or None.
        """
        return self._one(_SELECT_BY_ATTRIBUTES, source, size, mtime)

    def record(self, entry: Entry) -> None:
        """Commit a saved file's row; the remote is disposed only after.

        Args:
            entry: The file as saved locally.
        """
        self._db.execute(
            _INSERT,
            (
                entry.source,
                entry.sha256,
                entry.size,
                entry.mtime,
                entry.local_path,
                int(entry.disposed),
            ),
        )

    def mark_disposed(self, entry: Entry) -> None:
        """Record that the remote copy was deleted or moved.

        Args:
            entry: The saved file whose remote copy is gone.
        """
        self._db.execute(_DISPOSED, (entry.source, entry.sha256))
