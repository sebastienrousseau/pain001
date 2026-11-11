# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``pain001 <command> --format json | jq .`` works for every command.

Standard output carries the result and nothing else; the banner,
progress, warnings and errors go to standard error.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner, Result

from pain001.cli._format import Reporter
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR

MTYPE = "pain.001.001.09"
BUNDLE = TEMPLATES_DIR / MTYPE
PAIN002 = Path(__file__).resolve().parent.parent / (
    "pain001/test_fixtures/pain002_v15_sample.xml"
)
#: Commands that run a server and print no result.
SERVERS = {("serve",), ("mcp",)}


def _leaf_paths(
    group: click.Group, prefix: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    """Every runnable command under ``group``, as its path of names."""
    paths = []
    for name, command in group.commands.items():
        if isinstance(command, click.Group):
            paths.extend(_leaf_paths(command, (*prefix, name)))
        else:
            paths.append((*prefix, name))
    return paths


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory with the bundled sample data and example XML."""
    monkeypatch.chdir(tmp_path)
    shutil.copyfile(BUNDLE / "template.csv", "payments.csv")
    shutil.copyfile(BUNDLE / f"{MTYPE}.xml", "example.xml")
    return tmp_path


def _signed(workdir: Path) -> list[str]:
    """A signed file and the options that verify it."""
    from cryptography.hazmat.primitives.asymmetric import ec

    from pain001.security.dsig import sign_xml_document
    from tests.test_cli_verify_signature import DOC, _write_key_and_cert

    key, cert = _write_key_and_cert(
        workdir, ec.generate_private_key(ec.SECP256R1()), "signer"
    )
    Path("signed.xml").write_text(
        sign_xml_document(DOC, key.read_bytes(), cert.read_bytes()),
        encoding="utf-8",
    )
    return ["signed.xml", "--trust-embedded-cert"]


def _upload(workdir: Path) -> list[str]:
    """Upload with the transport stubbed: the receipt is the result."""
    from pain001.transport import sftp

    receipt = sftp.UploadResult("/inbox/example.xml", "ab" * 32, False)
    patcher = patch.object(sftp, "upload_sftp", return_value=receipt)
    patcher.start()
    return ["example.xml", "--sftp", "sftp://ops@bank.example/inbox/"]


def _download(workdir: Path) -> list[str]:
    """Download with the transport stubbed."""
    from pain001.transport import download

    result = download.DownloadResult(
        (download.Fetched("/out/a.xml", "a.xml", "cd" * 32, 3, "saved"),),
        ("odd\x1bname",),
        1,
    )
    patch.object(download, "download_sftp", return_value=result).start()
    return ["--sftp", "sftp://ops@h/outbox/", "--to", str(workdir)]


#: How to run each command so it succeeds in ``workdir``.
INVOCATIONS: dict[tuple[str, ...], Callable[[Path], list[str]]] = {
    ("generate",): lambda _: ["-t", MTYPE, "-d", "payments.csv", "-o", "out"],
    ("validate",): lambda _: ["-t", MTYPE, "-d", "payments.csv"],
    ("check",): lambda _: ["example.xml"],
    ("status",): lambda _: [str(PAIN002)],
    ("verify-signature",): _signed,
    ("face",): lambda _: ["example.xml", "--face", "iso_2018"],
    ("upload",): _upload,
    ("download",): _download,
    ("versions",): lambda _: [],
    ("inspect",): lambda _: [MTYPE],
    ("init",): lambda _: [MTYPE, "-o", "starter.csv"],
    ("plugins", "list"): lambda _: [],
    ("plugins", "show"): lambda _: ["csv"],
    ("plugins", "disable"): lambda _: ["parquet"],
}


#: The sample pain.002 rejects a transaction: ``status`` exits 3.
EXIT = {("status",): 3}


def _json(path: tuple[str, ...], args: list[str]) -> Any:
    """Run ``path`` with ``--format json``; return its parsed stdout."""
    result = CliRunner().invoke(cli, [*path, *args, "--format", "json"])
    assert result.exit_code == EXIT.get(path, 0), result.output
    return json.loads(result.stdout)


def test_every_command_is_covered() -> None:
    """A new command must say how it runs here, or be a server."""
    assert set(_leaf_paths(cli)) == set(INVOCATIONS) | SERVERS


@pytest.mark.parametrize("path", sorted(INVOCATIONS), ids=" ".join)
def test_format_json_is_one_document_on_stdout(
    workdir: Path, path: tuple[str, ...]
) -> None:
    """The audit's acceptance: ``pain001 <cmd> --format json | jq .``."""
    try:
        assert _json(path, INVOCATIONS[path](workdir)) is not None
    finally:
        patch.stopall()


def test_generate_reports_what_it_wrote(workdir: Path) -> None:
    """The result names the files, the type and the data."""
    payload = _json(("generate",), INVOCATIONS[("generate",)](workdir))
    assert payload["ok"] is True
    assert payload["message_type"] == MTYPE
    assert payload["files"] == [
        str(workdir.resolve() / "out" / f"{MTYPE}.xml")
    ]


def test_validate_with_a_scheme_embeds_its_result(workdir: Path) -> None:
    """The scheme result is part of the one object, not printed alone."""
    result = CliRunner().invoke(
        cli,
        [
            "validate",
            "-t",
            MTYPE,
            "-d",
            "payments.csv",
            "--scheme",
            "anti-duplicate",
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["records"] > 0
    assert payload["scheme"]["profile"] == "anti-duplicate"
    assert "Validating against scheme" not in result.output


def test_a_failure_is_still_one_json_document(workdir: Path) -> None:
    """``ok`` is false, ``error`` says why, the exit code is kept."""
    result = CliRunner().invoke(
        cli, ["validate", "-t", MTYPE, "-d", "missing.csv", "--format", "json"]
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "Input file not found: missing.csv"


def test_a_configuration_error_is_still_one_json_document(
    workdir: Path,
) -> None:
    """A usage error from the configuration is reported the same way."""
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            MTYPE,
            "-d",
            "payments.csv",
            "--profile",
            "no-such-profile",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "no-such-profile" in payload["error"]


@pytest.mark.parametrize(
    "flag",
    [["--list-templates"], ["--show-template", MTYPE], ["--show-config"]],
)
def test_generate_introspection_flags_print_json(
    workdir: Path, flag: list[str]
) -> None:
    """``--list-templates``, ``--show-template``, ``--show-config``."""
    payload = _json(("generate",), ["-t", MTYPE, "-d", "payments.csv", *flag])
    assert MTYPE in json.dumps(payload)


def test_show_config_text_goes_to_stdout(workdir: Path) -> None:
    """The resolved configuration is the result, so it is on stdout."""
    result = CliRunner().invoke(
        cli, ["generate", "-t", MTYPE, "-d", "payments.csv", "--show-config"]
    )
    assert result.exit_code == 0, result.output
    assert "template" in result.stdout


def test_progress_is_on_stderr_and_quiet_silences_it(workdir: Path) -> None:
    """Progress lines never reach stdout; ``-q`` drops them."""
    args = ["validate", "-t", MTYPE, "-d", "payments.csv", "-v"]
    loud = CliRunner().invoke(cli, args)
    assert loud.exit_code == 0, loud.output
    assert loud.stdout == ""
    assert "Data validation passed" in loud.stderr
    quiet = CliRunner().invoke(cli, [*args, "-q", "--log-format", "text"])
    assert "Data validation passed" not in quiet.stderr
    assert "Verbose logging enabled" not in quiet.stderr


def test_quiet_init_says_nothing(workdir: Path) -> None:
    """``init -q`` writes the file and prints nothing."""
    result = CliRunner().invoke(cli, ["init", MTYPE, "-o", "s.csv", "-q"])
    assert result.exit_code == 0
    assert result.output == ""
    assert Path("s.csv").is_file()


def test_metrics_are_json_lines_on_stdout(workdir: Path) -> None:
    """``--emit-metrics`` writes NDJSON; every stdout line parses."""
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-t",
            MTYPE,
            "-d",
            "payments.csv",
            "--emit-metrics",
            "--format",
            "json",
        ],
    )
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert any("metric" in line for line in lines)
    assert lines[-1]["ok"] is True


@pytest.mark.parametrize(
    "path",
    [("versions",), ("inspect", MTYPE), ("plugins", "list")],
    ids=" ".join,
)
def test_the_old_json_flag_still_works_and_warns(
    path: tuple[str, ...],
) -> None:
    """``--json`` is ``--format json`` for one more release."""
    result = CliRunner().invoke(cli, [*path, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)
    assert "--json is deprecated" in result.stderr
    assert "--format json" in result.stderr


def test_scheme_format_json_still_works_and_warns(workdir: Path) -> None:
    """``--scheme-format json`` keeps its output and warns on stderr."""
    result = CliRunner().invoke(
        cli,
        [
            "validate",
            "-t",
            MTYPE,
            "-d",
            "payments.csv",
            "--scheme",
            "anti-duplicate",
            "--scheme-format",
            "json",
        ],
    )
    assert json.loads(result.stdout)["profile"] == "anti-duplicate"
    assert "--scheme-format json is deprecated" in result.stderr


class _TTY(io.StringIO):
    """A stdout that says it is a terminal."""

    def isatty(self) -> bool:
        return True


def test_the_banner_is_for_a_terminal_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Shown on stderr when stdout is a TTY; never quiet or in JSON."""
    Reporter().banner()
    assert capsys.readouterr().err == ""
    monkeypatch.setattr(sys, "stdout", _TTY())
    Reporter(quiet=True).banner()
    Reporter("json").banner()
    assert capsys.readouterr().err == ""
    Reporter().banner()
    assert "Pain001" in capsys.readouterr().err


def test_face_json_with_an_output_file_names_it(workdir: Path) -> None:
    """The payload goes to the file; the object names the file."""
    payload = _json(
        ("face",), ["example.xml", "--face", "iso_2018", "-o", "face.json"]
    )
    assert payload["output"] == "face.json"
    assert payload["payload"] is None
    assert json.loads(Path("face.json").read_text(encoding="utf-8"))


def test_face_json_without_an_output_file_carries_the_payload(
    workdir: Path,
) -> None:
    """The loss report rides in the object instead of on stderr."""
    result = CliRunner().invoke(
        cli,
        ["face", "example.xml", "--face", "iso_2018", "--loss-report"]
        + ["--format", "json"],
    )
    payload = json.loads(result.stdout)
    assert payload["payload"]
    assert "unmapped_paths" in payload["loss_report"]
    assert "Face Loss Report" not in result.stderr


def test_upload_host_key_json() -> None:
    """``--print-host-key`` says the key is unverified, in JSON too."""
    with patch(
        "pain001.transport.sftp.print_host_fingerprint",
        return_value="SHA256:observed",
    ):
        payload = _json(
            ("upload",), ["--sftp", "sftp://o@h/in/", "--print-host-key"]
        )
    assert payload == {"fingerprint": "SHA256:observed", "verified": False}


def test_plugins_disable_json_without_a_name() -> None:
    """The variable and the examples, with no export line."""
    payload = _json(("plugins", "disable"), [])
    assert payload["variable"] == "PAIN001_DISABLE_PLUGINS"
    assert payload["export"] is None


def test_plugins_show_unknown_exits_1_on_stderr() -> None:
    """An unknown plugin is an error, not a result."""
    result = CliRunner().invoke(
        cli, ["plugins", "show", "nope", "--kind", "loader"]
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "No plugin named nope of kind loader" in result.stderr


def test_inspect_unknown_type_is_an_error_on_stderr() -> None:
    """Exit 2, nothing on stdout."""
    result: Result = CliRunner().invoke(
        cli, ["inspect", "pain.999.999.99", "--format", "json"]
    )
    assert result.exit_code == 2
    assert result.stdout == ""
