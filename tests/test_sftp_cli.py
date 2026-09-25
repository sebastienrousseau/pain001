# SPDX-License-Identifier: Apache-2.0 OR MIT
"""SFTP CLI options never put secrets in URLs or diagnostics."""

import builtins
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli

pytest.importorskip("paramiko")

from pain001.transport.sftp import UploadResult  # noqa: E402


@pytest.mark.parametrize(
    "reused,expected", [(False, "Uploaded:"), (True, "Already delivered:")]
)
def test_upload_command(tmp_path, monkeypatch, reused, expected):
    """Options arrive at the transport and secrets are absent from output."""
    source = tmp_path / "payments.xml"
    source.write_text("<Document/>")
    monkeypatch.setenv("TEST_SFTP_PASSWORD", "secret-value")
    monkeypatch.setenv("TEST_SFTP_PASSPHRASE", "passphrase-value")
    with patch(
        "pain001.transport.sftp.upload_sftp",
        return_value=UploadResult("/inbox/payments.xml", "abc", reused),
    ) as send:
        result = CliRunner().invoke(
            cli,
            [
                "upload",
                "--sftp",
                "sftp://ops@bank.example/inbox/",
                "--password-env",
                "TEST_SFTP_PASSWORD",
                "--passphrase-env",
                "TEST_SFTP_PASSPHRASE",
                str(source),
            ],
        )
    assert result.exit_code == 0, result.output
    assert expected in result.output
    assert "secret-value" not in result.output
    assert "passphrase-value" not in result.output
    assert send.call_args.kwargs["password"] == "secret-value"
    assert send.call_args.kwargs["passphrase"] == "passphrase-value"


def test_key_inspection_needs_no_secret_or_file():
    """The first-trust helper is explicitly labelled as unverified."""
    with (
        patch(
            "pain001.transport.sftp.print_host_fingerprint",
            return_value="SHA256:observed",
        ) as inspect,
        patch("pain001.transport.sftp.upload_sftp") as send,
    ):
        result = CliRunner().invoke(
            cli,
            [
                "upload",
                "--sftp",
                "sftp://ops@bank.example/inbox/",
                "--print-host-key",
                "--password-env",
                "UNSET_UNUSED_SECRET",
            ],
        )
    assert result.exit_code == 0
    assert "SHA256:observed" in result.output
    assert "Unverified" in result.output
    inspect.assert_called_once()
    send.assert_not_called()


def test_upload_requires_file():
    """Omitting a source file is a usage error, not a network attempt."""
    result = CliRunner().invoke(
        cli, ["upload", "--sftp", "sftp://ops@bank.example/inbox/"]
    )
    assert result.exit_code == 2
    assert "FILE_PATH is required" in result.output


def test_no_secret_options_and_transport_error(tmp_path):
    """SSH errors become clear nonzero CLI results."""
    source = tmp_path / "payments.xml"
    source.write_text("<Document/>")
    with patch(
        "pain001.transport.sftp.upload_sftp",
        side_effect=OSError("host key mismatch"),
    ) as send:
        result = CliRunner().invoke(
            cli,
            [
                "upload",
                "--sftp",
                "sftp://ops@bank.example/inbox/",
                str(source),
            ],
        )
    assert result.exit_code == 1
    assert "host key mismatch" in result.output
    assert send.call_args.kwargs["password"] is None


def test_missing_secret_is_not_silently_ignored(tmp_path, monkeypatch):
    """A misspelled environment-variable name cannot switch auth methods."""
    source = tmp_path / "payments.xml"
    source.write_text("<Document/>")
    monkeypatch.delenv("TEST_MISSING_SFTP_SECRET", raising=False)
    with patch("pain001.transport.sftp.upload_sftp") as send:
        result = CliRunner().invoke(
            cli,
            [
                "upload",
                "--sftp",
                "sftp://ops@bank.example/inbox/",
                "--password-env",
                "TEST_MISSING_SFTP_SECRET",
                str(source),
            ],
        )
    assert result.exit_code == 1
    assert "not set or is empty" in result.output
    send.assert_not_called()


def test_missing_optional_dependency(tmp_path):
    """A base installation gets an actionable optional-extra hint."""
    source = tmp_path / "payments.xml"
    source.write_text("<Document/>")
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "pain001.transport.sftp":
            raise ImportError("paramiko unavailable")
        return original(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=guarded):
        result = CliRunner().invoke(
            cli,
            [
                "upload",
                "--sftp",
                "sftp://ops@bank.example/inbox/",
                str(source),
            ],
        )
    assert result.exit_code == 1
    assert "pain001[upload]" in result.output
