# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Pin the exact values ``pain001.cli._logging`` produces.

The end-to-end tests in ``test_cli_logging.py`` show records reach
stderr, but they compare messages with ``in`` and only ever create a
log file one directory deep, so the mutation run's survivors (a
changed default, a dropped ``mkdir`` flag, a different file encoding,
a reworded error) were killed only incidentally. These tests call the
helpers directly and compare every value exactly.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import click
import pytest
from rich.console import Console

from pain001.cli import _logging
from pain001.cli._logging import (
    FORMATS,
    _env_choice,
    _handlers,
    configure_logging,
    resolve_log_format,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test without the logging variables, in an empty cwd."""
    monkeypatch.chdir(tmp_path)
    for name in ("LEVEL", "FILE", "FORMAT"):
        monkeypatch.delenv(f"PAIN001_LOG_{name}", raising=False)


def _built(monkeypatch: pytest.MonkeyPatch, path: Path) -> list[str]:
    """Build handlers logging to ``path``; return their encodings."""
    monkeypatch.setenv("PAIN001_LOG_FILE", str(path))
    handlers = _handlers(logging.INFO, "text")
    try:
        return [str(getattr(h, "encoding", "")) for h in handlers[1:]]
    finally:
        for handler in handlers:
            handler.close()


def test_bad_env_value_message_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The usage error lists the choices separated by a comma."""
    monkeypatch.setenv("PAIN001_LOG_FORMAT", "xml")
    with pytest.raises(click.UsageError) as caught:
        _env_choice("PAIN001_LOG_FORMAT", FORMATS, "text")
    assert caught.value.message == (
        "Environment variable PAIN001_LOG_FORMAT='xml' is not valid; "
        "use one of: text, json."
    )


def test_log_format_defaults_to_text() -> None:
    """With no flag and no variable the format is exactly ``text``."""
    assert resolve_log_format(None) == "text"


def test_no_log_file_means_one_handler(tmp_path: Path) -> None:
    """Without ``PAIN001_LOG_FILE`` only stderr is used, no file made."""
    handlers = _handlers(logging.INFO, "text")
    for handler in handlers:
        handler.close()
    assert len(handlers) == 1
    assert list(tmp_path.iterdir()) == []


def test_log_file_parents_are_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Missing parent directories, several deep, are created."""
    path = tmp_path / "a" / "b" / "run.log"
    _built(monkeypatch, path)
    assert path.is_file()


def test_log_file_parent_may_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A parent directory that already exists is not an error."""
    (tmp_path / "logs").mkdir()
    path = tmp_path / "logs" / "run.log"
    _built(monkeypatch, path)
    assert path.is_file()


def test_log_file_is_utf8(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The file handler writes UTF-8 whatever the locale says."""
    assert _built(monkeypatch, tmp_path / "run.log") == ["utf-8"]


def test_verbose_notice_is_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--verbose`` prints exactly one notice line on the console."""
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        _logging,
        "attach_cli_logging",
        lambda *args: calls.append(args),
    )
    console = Console(record=True, width=80, file=io.StringIO())
    configure_logging(console, True, "json")
    assert console.export_text() == "ℹ Verbose logging enabled\n"
    assert calls[0][1:] == (True, "json")
