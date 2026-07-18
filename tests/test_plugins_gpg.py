# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for the GPG-decrypting built-in loader (v0.0.54 issue #3).

Decryption itself is mocked - the tests verify the composition
contract (decrypt -> dispatch by inner extension -> tempfile
cleanup -> source-hint preservation) without needing a real `gpg`
binary in CI.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

from pain001.exceptions import DataSourceError
from pain001.plugins import PAIN001_API_VERSION, LoaderResult
from pain001.plugins.builtins_gpg import (
    GpgDecryptError,
    _GpgDecryptingLoader,
    _inner_extension,
    _secure_tempfile,
    _secure_tempfile_dir,
    maybe_register,
)
from pain001.plugins.registry import PluginRegistry


# ---------------------------------------------------------------------------
# _inner_extension
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path, expected",
    [
        ("batch.csv.gpg", ".csv"),
        ("batch.JSON.GPG", ".json"),
        ("batch.csv.asc", ".csv"),
        ("batch.jsonl.gpg", ".jsonl"),
        ("sealed.gpg", ""),
        ("payments.csv", ""),
        ("no-ext", ""),
    ],
)
def test_inner_extension_strips_outer_suffix(path, expected):
    """_inner_extension returns the inner ext when there is one, else ''."""
    assert _inner_extension(path) == expected


# ---------------------------------------------------------------------------
# _secure_tempfile_dir
# ---------------------------------------------------------------------------
def test_secure_tempfile_dir_prefers_dev_shm_on_linux(monkeypatch):
    """On Linux with /dev/shm writable, that directory is preferred."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os.path, "isdir", lambda p: p == "/dev/shm")
    monkeypatch.setattr(os, "access", lambda p, mode: p == "/dev/shm")
    assert _secure_tempfile_dir() == "/dev/shm"


def test_secure_tempfile_dir_falls_back_when_dev_shm_unwritable(monkeypatch):
    """If /dev/shm is missing or read-only, fall back to the platform default."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os.path, "isdir", lambda p: False)
    fallback = _secure_tempfile_dir()
    assert fallback != "/dev/shm"


def test_secure_tempfile_dir_uses_platform_default_on_non_linux(monkeypatch):
    """On macOS / Windows, never touch /dev/shm."""
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _secure_tempfile_dir() != "/dev/shm"


# ---------------------------------------------------------------------------
# _secure_tempfile context manager
# ---------------------------------------------------------------------------
def test_secure_tempfile_writes_and_unlinks(tmp_path, monkeypatch):
    """The temp file is materialised on enter and unlinked on exit."""
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._secure_tempfile_dir",
        lambda: str(tmp_path),
    )
    captured: dict = {}
    with _secure_tempfile(b"hello", ".csv") as path:
        captured["path"] = path
        assert os.path.isfile(path)
        with open(path, "rb") as fh:
            assert fh.read() == b"hello"
        # File mode is 0o600.
        assert (os.stat(path).st_mode & 0o777) == 0o600
        # Suffix preserved.
        assert path.endswith(".csv")
    # Unlinked after exit.
    assert not os.path.exists(captured["path"])


def test_secure_tempfile_unlinks_even_when_body_raises(tmp_path, monkeypatch):
    """Exceptions inside the with-block don't leak the plaintext file."""
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._secure_tempfile_dir",
        lambda: str(tmp_path),
    )
    holder: dict = {}
    with pytest.raises(RuntimeError):
        with _secure_tempfile(b"secret", ".json") as path:
            holder["path"] = path
            raise RuntimeError("inner loader exploded")
    assert not os.path.exists(holder["path"])


def test_secure_tempfile_exit_without_enter_is_a_noop():
    """__exit__ before a successful __enter__ does nothing (defensive guard)."""
    ctx = _secure_tempfile(b"x", ".csv")
    # __enter__ never ran; self._path is None. __exit__ must not raise.
    ctx.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Loader: end-to-end via mocked decryption
# ---------------------------------------------------------------------------
@pytest.fixture
def encrypted_csv(tmp_path):
    """A fake ciphertext file at <tmp>/batch.csv.gpg."""
    enc = tmp_path / "batch.csv.gpg"
    enc.write_bytes(b"ciphertext-placeholder")
    return str(enc)


@pytest.fixture
def isolated_registry(monkeypatch):
    """A pristine registry exposed to the GPG loader's dispatch.

    The GPG loader resolves the inner loader via the *global*
    singleton, so we patch the singleton's storage with a registry
    populated only with the built-in loaders we want to exercise.
    Restored after the test runs.
    """
    from pain001.plugins.registry import registry as global_registry

    global_registry.reset()
    global_registry._ensure_populated()
    yield global_registry
    global_registry.reset()


def test_gpg_loader_decrypts_and_dispatches_csv(
    encrypted_csv, isolated_registry, tmp_path, monkeypatch
):
    """A .csv.gpg flows decrypt -> _secure_tempfile -> csv loader."""
    plaintext_csv = b"id,amount\nA,1.00\nB,2.00\n"
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._decrypt_to_bytes",
        lambda ciphertext: plaintext_csv,
    )
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._secure_tempfile_dir",
        lambda: str(tmp_path),
    )
    result = _GpgDecryptingLoader().load(encrypted_csv)
    assert isinstance(result, LoaderResult)
    assert len(result.rows) == 2
    # source_hint is rewritten to the encrypted-file path so findings
    # point at what the user actually passed in.
    assert result.source_hint == encrypted_csv


def test_gpg_loader_dispatches_json(tmp_path, isolated_registry, monkeypatch):
    """Inner-extension dispatch picks the JSON loader for .json.gpg."""
    enc = tmp_path / "batch.json.gpg"
    enc.write_bytes(b"ciphertext")
    plaintext_json = json.dumps([{"id": "A"}, {"id": "B"}]).encode()
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._decrypt_to_bytes",
        lambda ciphertext: plaintext_json,
    )
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._secure_tempfile_dir",
        lambda: str(tmp_path),
    )
    result = _GpgDecryptingLoader().load(str(enc))
    assert [row["id"] for row in result.rows] == ["A", "B"]


def test_gpg_loader_rejects_filename_without_inner_extension(
    tmp_path, monkeypatch
):
    """`sealed.gpg` alone is rejected with a clear DataSourceError."""
    enc = tmp_path / "sealed.gpg"
    enc.write_bytes(b"ciphertext")
    with pytest.raises(DataSourceError, match="Cannot infer inner format"):
        _GpgDecryptingLoader().load(str(enc))


def test_gpg_loader_rejects_when_inner_loader_missing(
    tmp_path, isolated_registry, monkeypatch
):
    """No loader for `.xyz` -> a clear "install a plugin" error."""
    enc = tmp_path / "batch.xyz.gpg"
    enc.write_bytes(b"ciphertext")
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._decrypt_to_bytes",
        lambda ciphertext: b"any plaintext",
    )
    with pytest.raises(DataSourceError, match="no inner loader registered"):
        _GpgDecryptingLoader().load(str(enc))


def test_gpg_loader_streaming_passes_chunks_through(
    encrypted_csv, isolated_registry, tmp_path, monkeypatch
):
    """Streaming variant yields chunks via the inner loader."""
    plaintext_csv = b"id,amount\nA,1.00\nB,2.00\nC,3.00\n"
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._decrypt_to_bytes",
        lambda ciphertext: plaintext_csv,
    )
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._secure_tempfile_dir",
        lambda: str(tmp_path),
    )
    chunks = list(
        _GpgDecryptingLoader().load_streaming(encrypted_csv, chunk_size=1)
    )
    assert chunks
    assert all(c.source_hint == encrypted_csv for c in chunks)


def test_gpg_loader_streaming_rejects_filename_without_inner_extension(
    tmp_path,
):
    """Streaming variant also enforces the `<name>.<inner>.gpg` shape."""
    enc = tmp_path / "sealed.gpg"
    enc.write_bytes(b"ciphertext")
    with pytest.raises(DataSourceError, match="Cannot infer inner format"):
        list(_GpgDecryptingLoader().load_streaming(str(enc), chunk_size=10))


def test_gpg_loader_streaming_rejects_when_inner_loader_missing(
    tmp_path, isolated_registry, monkeypatch
):
    """Streaming variant surfaces the same "install a plugin" error."""
    enc = tmp_path / "batch.xyz.gpg"
    enc.write_bytes(b"ciphertext")
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._decrypt_to_bytes",
        lambda ciphertext: b"any plaintext",
    )
    with pytest.raises(DataSourceError, match="no inner loader registered"):
        list(_GpgDecryptingLoader().load_streaming(str(enc), chunk_size=10))


# ---------------------------------------------------------------------------
# Decryption failure surface
# ---------------------------------------------------------------------------
def test_decrypt_to_bytes_raises_gpg_decrypt_error_on_failure(monkeypatch):
    """A failed gnupg.GPG().decrypt call surfaces a GpgDecryptError."""
    fake_result = MagicMock()
    fake_result.__bool__ = lambda self: False
    fake_result.status = "no secret key"
    fake_gpg_instance = MagicMock()
    fake_gpg_instance.decrypt.return_value = fake_result
    fake_gpg_module = MagicMock()
    fake_gpg_module.GPG.return_value = fake_gpg_instance
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._gpg_module",
        lambda: fake_gpg_module,
    )
    from pain001.plugins.builtins_gpg import _decrypt_to_bytes

    with pytest.raises(GpgDecryptError, match="no secret key"):
        _decrypt_to_bytes(b"ciphertext")


def test_decrypt_to_bytes_respects_homedir_and_passphrase_env(monkeypatch):
    """PAIN001_GPG_HOMEDIR + PAIN001_GPG_PASSPHRASE_ENV are honoured."""
    fake_result = MagicMock()
    fake_result.__bool__ = lambda self: True
    fake_result.data = b"plaintext"
    fake_gpg_instance = MagicMock()
    fake_gpg_instance.decrypt.return_value = fake_result
    fake_gpg_module = MagicMock()
    fake_gpg_module.GPG.return_value = fake_gpg_instance
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._gpg_module",
        lambda: fake_gpg_module,
    )
    monkeypatch.setenv("PAIN001_GPG_HOMEDIR", "/tmp/fake-gpg-home")
    monkeypatch.setenv("PAIN001_GPG_PASSPHRASE_ENV", "MY_PASS")
    monkeypatch.setenv("MY_PASS", "s3cret")
    from pain001.plugins.builtins_gpg import _decrypt_to_bytes

    result = _decrypt_to_bytes(b"ciphertext")
    assert result == b"plaintext"
    fake_gpg_module.GPG.assert_called_once_with(gnupghome="/tmp/fake-gpg-home")
    fake_gpg_instance.decrypt.assert_called_once_with(
        b"ciphertext", passphrase="s3cret"
    )


def test_gpg_module_import_error_wraps_as_data_source_error(monkeypatch):
    """Missing python-gnupg -> a DataSourceError pointing at the gpg extra."""
    monkeypatch.setitem(sys.modules, "gnupg", None)
    from pain001.plugins.builtins_gpg import _gpg_module

    with pytest.raises(DataSourceError, match="pain001\\[gpg\\]"):
        _gpg_module()


def test_gpg_module_returns_imported_module_when_present(monkeypatch):
    """When python-gnupg is importable, _gpg_module returns the module."""
    fake_module = MagicMock(name="fake_gnupg")
    monkeypatch.setitem(sys.modules, "gnupg", fake_module)
    from pain001.plugins.builtins_gpg import _gpg_module

    assert _gpg_module() is fake_module


# ---------------------------------------------------------------------------
# Plugin metadata + conditional registration
# ---------------------------------------------------------------------------
def test_loader_meta_is_well_formed():
    """meta carries the expected name, source, api_version, extensions."""
    loader = _GpgDecryptingLoader()
    assert loader.meta.name == "gpg"
    assert loader.meta.source == "built-in"
    assert loader.meta.api_version == PAIN001_API_VERSION
    assert loader.extensions == (".gpg", ".asc")


def test_maybe_register_no_op_when_gnupg_missing(monkeypatch):
    """Without python-gnupg installed, maybe_register adds nothing."""
    monkeypatch.setitem(sys.modules, "gnupg", None)
    reg = PluginRegistry(PAIN001_API_VERSION)
    maybe_register(reg)
    reg._populated = True
    assert reg.get_loader("gpg") is None


def test_maybe_register_adds_loader_when_gnupg_present(monkeypatch):
    """With python-gnupg importable, maybe_register adds the GPG loader."""
    fake_module = MagicMock()
    monkeypatch.setitem(sys.modules, "gnupg", fake_module)
    reg = PluginRegistry(PAIN001_API_VERSION)
    maybe_register(reg)
    reg._populated = True
    assert reg.get_loader("gpg") is not None
