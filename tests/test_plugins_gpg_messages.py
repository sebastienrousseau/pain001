# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Operator-facing messages and file handling of the GPG loader.

``gnupg`` is replaced by an in-memory stand-in, so these tests pin the
exact guidance a user gets on each failure, what bytes reach gpg, and
how the plaintext temp file is named and placed, without a ``gpg``
binary.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from pain001.exceptions import DataSourceError
from pain001.plugins import LoaderResult, builtins_gpg
from pain001.plugins._registration import BuiltinRegistry
from pain001.plugins.builtins_gpg import (
    GpgDecryptError,
    _GpgDecryptingLoader,
    _secure_tempfile,
)

LOGGER = "pain001.plugins.builtins_gpg"
CHECK_TAIL = (
    ". Check PAIN001_GPG_HOMEDIR, PAIN001_GPG_PASSPHRASE_ENV / "
    "--decrypt-passphrase-env, PAIN001_GPG_KEYFILE / --decrypt-key, "
    "and that the matching secret key is available in the keyring."
)


class _FakeGPG:
    """``gnupg.GPG`` stand-in that records ciphertext it is given."""

    seen: list[Any] = []
    result: Any = None
    import_count: Any = 1

    def __init__(self, gnupghome: str | None = None) -> None:
        """Accept the homedir argument the loader passes."""
        self.gnupghome = gnupghome

    def decrypt(self, ciphertext: Any, passphrase: Any = None) -> Any:
        """Record ``ciphertext`` and return the configured result."""
        _FakeGPG.seen.append(ciphertext)
        return _FakeGPG.result

    def import_keys(self, material: bytes) -> Any:
        """Report the configured number of imported keys."""
        return SimpleNamespace(count=_FakeGPG.import_count)


class _OkResult:
    """Truthy decrypt result carrying plaintext."""

    def __init__(self, data: bytes) -> None:
        """Store ``data`` as the plaintext."""
        self.data = data

    def __bool__(self) -> bool:
        """Report success."""
        return True


class _FailNoStatus:
    """Falsy decrypt result with no ``status`` attribute."""

    def __bool__(self) -> bool:
        """Report failure."""
        return False


class _FailWithStatus(_FailNoStatus):
    """Falsy decrypt result that carries gpg's ``status`` text."""

    def __init__(self, status: str) -> None:
        """Keep the status gpg reported."""
        self.status = status


@pytest.fixture
def fake_gnupg(monkeypatch: pytest.MonkeyPatch) -> type[_FakeGPG]:
    """Install the stand-in ``gnupg`` module and a clean environment."""
    _FakeGPG.seen = []
    _FakeGPG.result = _OkResult(b"id\n1\n")
    _FakeGPG.import_count = 1
    monkeypatch.setitem(sys.modules, "gnupg", SimpleNamespace(GPG=_FakeGPG))
    for var in ("PAIN001_GPG_HOMEDIR", "PAIN001_GPG_KEYFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)
    return _FakeGPG


class _Inner:
    """Inner loader that records the temp file it was handed."""

    def __init__(self) -> None:
        """Start with nothing seen."""
        self.paths: list[str] = []
        self.contents: list[bytes] = []

    def load(self, path: str) -> LoaderResult:
        """Record ``path`` and its bytes; return one row."""
        self.paths.append(path)
        self.contents.append(Path(path).read_bytes())
        return LoaderResult(rows=[{"id": "1"}], source_hint=path)

    def load_streaming(self, path: str, chunk_size: int) -> Any:
        """Record ``path`` and yield one chunk."""
        self.paths.append(path)
        self.contents.append(Path(path).read_bytes())
        yield LoaderResult(rows=[{"id": "1"}], source_hint=path)


def _loader(inner: Any) -> _GpgDecryptingLoader:
    """Return a GPG loader whose registry resolves to ``inner``."""
    registry = SimpleNamespace(get_loader_for_extension=lambda ext: inner)
    return _GpgDecryptingLoader(cast("BuiltinRegistry", registry))


def test_missing_gnupg_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without python-gnupg the error explains how to install it."""
    monkeypatch.setitem(sys.modules, "gnupg", None)
    with pytest.raises(DataSourceError) as info:
        builtins_gpg._gpg_module()
    assert str(info.value) == (
        "The pain001[gpg] extra is required to read .gpg / .asc files; "
        "install with `pip install pain001[gpg]` and ensure the `gpg` "
        "binary is on PATH."
    )


def test_maybe_register_without_gnupg_logs_and_skips(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """No extra, no loader, one debug line saying so."""
    monkeypatch.setitem(sys.modules, "gnupg", None)
    registered: list[Any] = []
    reg = SimpleNamespace(register_loader=registered.append)
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        builtins_gpg.maybe_register(cast("BuiltinRegistry", reg))
    assert registered == []
    assert [r.getMessage() for r in caplog.records] == [
        "pain001[gpg] extra not installed; .gpg / .asc loader unavailable"
    ]


def test_inner_extension_reads_the_suffix_before_gpg() -> None:
    """Only the suffix immediately inside ``.gpg`` is the inner format."""
    assert builtins_gpg._inner_extension("batch.v1.csv.gpg") == ".csv"
    assert builtins_gpg._inner_extension("batch.v1.csv.gpg.bak") == ""


def test_keyfile_import_logs_count_and_explains_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A good key file logs its count; an empty import says how to export."""
    keyfile = tmp_path / "key.asc"
    keyfile.write_bytes(b"material")
    gpg = _FakeGPG()
    _FakeGPG.import_count = 2
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        builtins_gpg._import_keyfile(gpg, str(keyfile))
    assert [r.getMessage() for r in caplog.records] == [
        "imported 2 key(s) from PAIN001_GPG_KEYFILE"
    ]
    _FakeGPG.import_count = 0
    with pytest.raises(GpgDecryptError) as info:
        builtins_gpg._import_keyfile(gpg, str(keyfile))
    assert str(info.value) == (
        f"GPG key file imported no keys: {keyfile}. Export the private "
        "key with `gpg --export-secret-keys --armor <id>`."
    )


def test_decrypt_failure_without_status_uses_generic_text(
    fake_gnupg: type[_FakeGPG],
) -> None:
    """A failed result with no status still yields full guidance."""
    fake_gnupg.result = _FailNoStatus()
    with pytest.raises(GpgDecryptError) as info:
        builtins_gpg._decrypt_to_bytes(b"cipher")
    assert str(info.value) == (
        "GPG decryption failed: decryption failed" + CHECK_TAIL
    )


def test_decrypt_failure_reports_gpg_status(
    fake_gnupg: type[_FakeGPG],
) -> None:
    """The gpg status string is quoted ahead of the guidance."""
    fake_gnupg.result = _FailWithStatus("no secret key")
    with pytest.raises(GpgDecryptError) as info:
        builtins_gpg._decrypt_to_bytes(b"cipher")
    assert (
        str(info.value) == "GPG decryption failed: no secret key" + CHECK_TAIL
    )


@pytest.mark.parametrize("streaming", [False, True])
def test_bad_name_message(streaming: bool) -> None:
    """A name without an inner extension explains the expected form."""
    loader = _loader(_Inner())
    form = "be of the form `<name>.<inner-ext>.gpg`"
    with pytest.raises(DataSourceError) as info:
        if streaming:
            list(loader.load_streaming("sealed.gpg", 10))
        else:
            loader.load("sealed.gpg")
    expected = (
        f"Cannot infer inner format for sealed.gpg: filename must {form}"
    )
    if streaming:
        assert str(info.value) == expected + "."
    else:
        assert str(info.value) == expected + " (e.g. `batch.csv.gpg`)."


def test_no_inner_loader_message() -> None:
    """An unknown inner format names it and suggests a fix."""
    loader = _loader(None)
    with pytest.raises(DataSourceError) as info:
        loader._dispatch(b"x", ".xyz", "p.xyz.gpg")
    assert str(info.value) == (
        "GPG loader: no inner loader registered for '.xyz' (got p.xyz.gpg). "
        "Install a plugin that handles that extension, or use a supported "
        "inner format."
    )


@pytest.mark.parametrize("streaming", [False, True])
def test_file_bytes_reach_gpg_and_plaintext_reaches_inner(
    streaming: bool,
    fake_gnupg: type[_FakeGPG],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw file bytes are decrypted; the inner loader gets a named temp."""
    monkeypatch.setattr(
        builtins_gpg, "_secure_tempfile_dir", lambda: str(tmp_path)
    )
    encrypted = tmp_path / "pay.csv.gpg"
    encrypted.write_bytes(b"\x85\x01binary\r\n")
    inner = _Inner()
    loader = _loader(inner)
    if streaming:
        results = list(loader.load_streaming(str(encrypted), 5))
    else:
        results = [loader.load(str(encrypted))]
    assert fake_gnupg.seen == [b"\x85\x01binary\r\n"]
    assert inner.contents == [b"id\n1\n"]
    temp = Path(inner.paths[0])
    assert temp.parent == tmp_path
    assert temp.name.startswith("pain001-gpg-")
    assert temp.suffix == ".csv"
    assert not temp.exists()
    assert [r.source_hint for r in results] == [str(encrypted)]


def test_secure_tempfile_is_owner_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plaintext file is placed in the secure dir with mode 0600."""
    monkeypatch.setattr(
        builtins_gpg, "_secure_tempfile_dir", lambda: str(tmp_path)
    )
    with _secure_tempfile(b"data", ".json") as path:
        assert os.path.dirname(path) == str(tmp_path)
        assert os.stat(path).st_mode & 0o777 == 0o600
        assert Path(path).read_bytes() == b"data"
    assert not os.path.exists(path)
