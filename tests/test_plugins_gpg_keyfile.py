# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""The ``--decrypt-key`` / ``--decrypt-passphrase-env`` flags (issue #181).

The GPG loader shipped configured by environment only. The issue's
spec names two CLI flags; they are sugar over ``PAIN001_GPG_KEYFILE``
and ``PAIN001_GPG_PASSPHRASE_ENV``, and the key-file variable is new:
it imports a private key into the homedir before decrypting, for
pipelines that hold the key in a secret store rather than a keyring.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli, main
from pain001.constants import TEMPLATES_DIR
from pain001.plugins.builtins_gpg import (
    GpgDecryptError,
    _decrypt_to_bytes,
    _import_keyfile,
)

_TPL = TEMPLATES_DIR / "pain.001.001.03"


def _fake_gpg_module(imported: int = 1) -> tuple[MagicMock, MagicMock]:
    """Build a fake ``gnupg`` module whose GPG() decrypts and imports."""
    decrypted = MagicMock()
    decrypted.__bool__ = lambda self: True
    decrypted.data = b"plaintext"
    import_result = MagicMock()
    import_result.count = imported
    instance = MagicMock()
    instance.decrypt.return_value = decrypted
    instance.import_keys.return_value = import_result
    module = MagicMock()
    module.GPG.return_value = instance
    return module, instance


def _base_args() -> list[str]:
    """CLI args pointing at the bundled pain.001.001.03 assets."""
    return [
        "-t",
        "pain.001.001.03",
        "-m",
        str(_TPL / "template.xml"),
        "-s",
        str(_TPL / "pain.001.001.03.xsd"),
        "-d",
        str(_TPL / "template.csv"),
    ]


# ---------------------------------------------------------------------------
# _import_keyfile
# ---------------------------------------------------------------------------
def test_import_keyfile_hands_the_file_bytes_to_gpg(tmp_path: Path) -> None:
    """The file's bytes go to ``import_keys`` untouched."""
    keyfile = tmp_path / "ops.asc"
    keyfile.write_bytes(b"-----BEGIN PGP PRIVATE KEY BLOCK-----\n...")
    _, instance = _fake_gpg_module(imported=1)

    _import_keyfile(instance, str(keyfile))

    instance.import_keys.assert_called_once_with(keyfile.read_bytes())


def test_import_keyfile_rejects_an_unreadable_path(tmp_path: Path) -> None:
    """A missing file is a ``GpgDecryptError`` naming the path."""
    _, instance = _fake_gpg_module()
    missing = tmp_path / "nope.asc"
    with pytest.raises(GpgDecryptError, match="could not be read") as excinfo:
        _import_keyfile(instance, str(missing))
    assert str(missing) in str(excinfo.value)
    instance.import_keys.assert_not_called()


def test_import_keyfile_rejects_a_file_that_imports_nothing(
    tmp_path: Path,
) -> None:
    """gpg importing zero keys is an error, not a silent no-op."""
    keyfile = tmp_path / "public-only.asc"
    keyfile.write_bytes(b"not a private key")
    _, instance = _fake_gpg_module(imported=0)
    with pytest.raises(GpgDecryptError, match="imported no keys"):
        _import_keyfile(instance, str(keyfile))


def test_import_keyfile_tolerates_a_result_without_a_count(
    tmp_path: Path,
) -> None:
    """An import result lacking ``count`` reads as zero keys."""
    keyfile = tmp_path / "k.asc"
    keyfile.write_bytes(b"x")
    instance = MagicMock()
    instance.import_keys.return_value = object()
    with pytest.raises(GpgDecryptError, match="imported no keys"):
        _import_keyfile(instance, str(keyfile))


# ---------------------------------------------------------------------------
# _decrypt_to_bytes honours PAIN001_GPG_KEYFILE
# ---------------------------------------------------------------------------
def test_decrypt_imports_the_keyfile_before_decrypting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With the env var set, the key is imported first, then decrypt runs."""
    keyfile = tmp_path / "ops.asc"
    keyfile.write_bytes(b"key material")
    module, instance = _fake_gpg_module(imported=1)
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._gpg_module", lambda: module
    )
    monkeypatch.setenv("PAIN001_GPG_KEYFILE", str(keyfile))
    monkeypatch.delenv("PAIN001_GPG_HOMEDIR", raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)

    assert _decrypt_to_bytes(b"ciphertext") == b"plaintext"

    instance.import_keys.assert_called_once_with(b"key material")
    instance.decrypt.assert_called_once_with(b"ciphertext", passphrase=None)
    # Import happened before decryption.
    calls = [c[0] for c in instance.method_calls]
    assert calls.index("import_keys") < calls.index("decrypt")


def test_decrypt_skips_the_import_when_no_keyfile_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the env var the keyring is used as before."""
    module, instance = _fake_gpg_module()
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._gpg_module", lambda: module
    )
    monkeypatch.delenv("PAIN001_GPG_KEYFILE", raising=False)
    monkeypatch.delenv("PAIN001_GPG_HOMEDIR", raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)

    assert _decrypt_to_bytes(b"ciphertext") == b"plaintext"
    instance.import_keys.assert_not_called()


def test_decrypt_failure_message_names_the_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The remediation hint points at both env vars and both flags."""
    failed = MagicMock()
    failed.__bool__ = lambda self: False
    failed.status = "no secret key"
    module, instance = _fake_gpg_module()
    instance.decrypt.return_value = failed
    monkeypatch.setattr(
        "pain001.plugins.builtins_gpg._gpg_module", lambda: module
    )
    monkeypatch.delenv("PAIN001_GPG_KEYFILE", raising=False)
    monkeypatch.delenv("PAIN001_GPG_HOMEDIR", raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)
    with pytest.raises(GpgDecryptError) as excinfo:
        _decrypt_to_bytes(b"ciphertext")
    text = str(excinfo.value)
    assert "--decrypt-key" in text
    assert "--decrypt-passphrase-env" in text
    assert "no secret key" in text


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------
def test_generate_flags_set_the_loader_env_vars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--decrypt-key`` / ``--decrypt-passphrase-env`` reach the loader."""
    keyfile = tmp_path / "ops.asc"
    keyfile.write_bytes(b"k")
    monkeypatch.delenv("PAIN001_GPG_KEYFILE", raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)

    with patch("pain001.cli.cli.load_payment_data", return_value=[{}]):
        result = CliRunner().invoke(
            main,
            [
                *_base_args(),
                "--decrypt-key",
                str(keyfile),
                "--decrypt-passphrase-env",
                "OPS_GPG_PASS",
                "--dry-run",
            ],
        )
    assert result.exit_code == 0, result.output
    assert os.environ["PAIN001_GPG_KEYFILE"] == str(keyfile)
    assert os.environ["PAIN001_GPG_PASSPHRASE_ENV"] == "OPS_GPG_PASS"
    assert "GPG key file" in result.output


def test_validate_subcommand_passes_the_flags_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``pain001 validate`` accepts the same two flags."""
    keyfile = tmp_path / "ops.asc"
    keyfile.write_bytes(b"k")
    monkeypatch.delenv("PAIN001_GPG_KEYFILE", raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)

    with patch("pain001.cli.cli.load_payment_data", return_value=[{}]):
        result = CliRunner().invoke(
            cli,
            [
                "validate",
                *_base_args(),
                "--decrypt-key",
                str(keyfile),
                "--decrypt-passphrase-env",
                "OPS_GPG_PASS",
            ],
        )
    assert result.exit_code == 0, result.output
    assert os.environ["PAIN001_GPG_KEYFILE"] == str(keyfile)
    assert os.environ["PAIN001_GPG_PASSPHRASE_ENV"] == "OPS_GPG_PASS"


def test_flags_are_optional_and_leave_the_environment_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the flags nothing is written to the environment."""
    monkeypatch.delenv("PAIN001_GPG_KEYFILE", raising=False)
    monkeypatch.delenv("PAIN001_GPG_PASSPHRASE_ENV", raising=False)
    with patch("pain001.cli.cli.load_payment_data", return_value=[{}]):
        result = CliRunner().invoke(main, [*_base_args(), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "PAIN001_GPG_KEYFILE" not in os.environ
    assert "PAIN001_GPG_PASSPHRASE_ENV" not in os.environ


def test_decrypt_key_must_name_an_existing_file(tmp_path: Path) -> None:
    """A missing key file is a usage error (exit 2) before any work."""
    result = CliRunner().invoke(
        main,
        [*_base_args(), "--decrypt-key", str(tmp_path / "nope.asc")],
    )
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_help_documents_both_flags() -> None:
    """The flags show up in ``--help`` for generate and validate."""
    for args in (["generate", "--help"], ["validate", "--help"]):
        result = CliRunner().invoke(cli, args)
        assert result.exit_code == 0
        assert "--decrypt-key" in result.output
        assert "--decrypt-passphrase-env" in result.output
