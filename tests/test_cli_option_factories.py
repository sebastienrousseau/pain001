# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The shared option decorators, applied to a fresh command in the test.

``ssh_options``, ``xml_sign_options`` and ``format_option`` run when the
CLI modules are imported, so a test that only drives the real commands
never runs them again. These tests apply each one to a new command and
pin what it attaches: the flags, their order in ``--help``, types,
defaults and help text. They are the CLI's contract (renaming or
retyping a flag is a breaking change), and they are what a wrong edit
to a decorator would change.
"""

from __future__ import annotations

from typing import Any

import click
import pytest
from click.testing import CliRunner

from pain001.cli._format import format_option
from pain001.cli._verify_signature import xml_sign_alg_option, xml_sign_options
from pain001.transport.cli import ssh_options


def _command(decorator: Any) -> click.Command:
    """Apply ``decorator`` to a no-op callback and wrap it in a command."""

    def callback(**_: Any) -> None:
        """Accept whatever the options pass."""

    return click.command()(decorator(callback))


def _received(decorator: Any, args: list[str] | None = None) -> dict[str, Any]:
    """The keyword arguments a decorated command receives for ``args``."""
    seen: dict[str, Any] = {}

    def callback(**kwargs: Any) -> None:
        """Record what Click passed."""
        seen.update(kwargs)

    result = CliRunner().invoke(
        click.command()(decorator(callback)), args or []
    )
    assert result.exit_code == 0, result.output
    return seen


def _option(command: click.Command, flag: str) -> click.Option:
    """The option ``flag`` names on ``command``."""
    for param in command.params:
        if isinstance(param, click.Option) and flag in param.opts:
            return param
    raise AssertionError(f"{flag} is not on the command")


def _path(param: click.Option) -> tuple[bool, bool, bool]:
    """``(exists, dir_okay, readable)`` of a ``click.Path`` option."""
    assert isinstance(param.type, click.Path)
    return (param.type.exists, param.type.dir_okay, param.type.readable)


def test_ssh_options_attach_the_eight_flags_in_order() -> None:
    """``--help`` lists the trust, identity and timeout flags in this order."""
    command = _command(ssh_options)
    assert [p.opts for p in command.params] == [
        ["--known-hosts"],
        ["--accept-host-key"],
        ["--identity-file"],
        ["--certificate"],
        ["--use-agent"],
        ["--password-env"],
        ["--passphrase-env"],
        ["--timeout"],
    ]
    assert [p.name for p in command.params] == [
        "known_hosts",
        "accept_host_key",
        "identity_file",
        "certificate",
        "use_agent",
        "password_env",
        "passphrase_env",
        "timeout",
    ]


@pytest.mark.parametrize(
    "flag", ["--known-hosts", "--identity-file", "--certificate"]
)
def test_ssh_file_flags_need_an_existing_file(flag: str) -> None:
    """Key, certificate and known_hosts must name a file that exists."""
    assert _path(_option(_command(ssh_options), flag)) == (True, False, True)


def test_ssh_value_flags_and_the_agent_switch() -> None:
    """The fingerprint and env-var names are strings; --use-agent is a flag."""
    command = _command(ssh_options)
    for flag in ("--accept-host-key", "--password-env", "--passphrase-env"):
        option = _option(command, flag)
        assert option.type is click.STRING, flag
        assert not option.is_flag, flag
    assert _option(command, "--use-agent").is_flag
    assert _received(ssh_options) == {
        "known_hosts": None,
        "accept_host_key": None,
        "identity_file": None,
        "certificate": None,
        "use_agent": False,
        "password_env": None,
        "passphrase_env": None,
        "timeout": 15,
    }
    given = _received(
        ssh_options,
        ["--accept-host-key", "SHA256:abc", "--use-agent", "--timeout", "2.5"],
    )
    assert given["accept_host_key"] == "SHA256:abc"
    assert given["use_agent"] is True
    assert given["timeout"] == 2.5


def test_ssh_timeout_is_bounded_and_shows_its_default() -> None:
    """--timeout takes 0.1 to 300 seconds and defaults to 15."""
    timeout = _option(_command(ssh_options), "--timeout")
    assert isinstance(timeout.type, click.FloatRange)
    assert (timeout.type.min, timeout.type.max) == (0.1, 300)
    assert timeout.default == 15
    assert timeout.show_default is True


def test_ssh_options_help_text() -> None:
    """Each flag says what it is for; the wording is part of --help."""
    command = _command(ssh_options)
    assert {
        o: _option(command, o).help
        for o in (
            "--known-hosts",
            "--accept-host-key",
            "--identity-file",
            "--certificate",
            "--use-agent",
            "--password-env",
            "--passphrase-env",
            "--timeout",
        )
    } == {
        "--known-hosts": "Trusted SSH known_hosts file.",
        "--accept-host-key": "Independently verified OpenSSH SHA256 "
        "fingerprint; never saves trust.",
        "--identity-file": "SSH private key; otherwise use the agent or "
        "default SSH keys.",
        "--certificate": "OpenSSH certificate (*-cert.pub) issued for "
        "--identity-file.",
        "--use-agent": "Also offer ssh-agent keys (hardware keys) with a "
        "key or password.",
        "--password-env": "Environment variable containing the SSH password.",
        "--passphrase-env": "Environment variable containing the "
        "private-key passphrase.",
        "--timeout": "Network timeout in seconds.",
    }


def test_xml_sign_options_attach_four_flags_in_order() -> None:
    """Key, certificate, algorithm and passphrase variable, in that order."""
    command = _command(xml_sign_options)
    assert [p.opts for p in command.params] == [
        ["--xml-sign-key"],
        ["--xml-sign-cert"],
        ["--xml-sign-alg"],
        ["--xml-sign-passphrase-env"],
    ]
    assert [p.name for p in command.params] == [
        "xml_sign_key",
        "xml_sign_cert",
        "xml_sign_alg",
        "xml_sign_passphrase_env",
    ]


@pytest.mark.parametrize("flag", ["--xml-sign-key", "--xml-sign-cert"])
def test_xml_sign_pem_flags_need_a_readable_file(flag: str) -> None:
    """The key and certificate must be existing, readable files."""
    option = _option(_command(xml_sign_options), flag)
    assert _path(option) == (True, False, True)
    assert option.default is None
    assert option.expose_value is True


def test_xml_sign_alg_goes_through_its_callback_not_a_parameter() -> None:
    """--xml-sign-alg is a choice handled by its callback, not passed on."""
    alg = _option(_command(xml_sign_options), "--xml-sign-alg")
    assert isinstance(alg.type, click.Choice)
    assert list(alg.type.choices) == sorted(alg.type.choices)
    assert "rsa-sha256" in alg.type.choices
    assert alg.expose_value is False
    assert alg.callback is xml_sign_alg_option


def test_xml_sign_passphrase_env_is_a_variable_name() -> None:
    """The passphrase comes from a named variable, shown as VAR."""
    env = _option(_command(xml_sign_options), "--xml-sign-passphrase-env")
    assert env.type is click.STRING
    assert env.default is None
    assert env.metavar == "VAR"


def test_xml_sign_options_help_text() -> None:
    """The signing flags' wording in --help."""
    command = _command(xml_sign_options)
    assert [p.help for p in command.params if isinstance(p, click.Option)] == [
        "Private key PEM file (RSA, or EC P-256/P-384) to sign the "
        "generated XML with W3C XML-DSig.",
        "Optional X.509 certificate PEM file to embed in XML-DSig <KeyInfo>.",
        "XML-DSig algorithm; default follows the key (RSA: rsa-sha256).",
        "Environment variable holding the passphrase for --xml-sign-key.",
    ]


def test_format_option_defaults_to_text_and_lists_its_choices() -> None:
    """--format offers text, json and the extras, text by default."""
    command = _command(format_option("csv"))
    (option,) = command.params
    assert option.opts == ["--format"]
    assert option.name == "output_format"
    assert isinstance(option.type, click.Choice)
    assert list(option.type.choices) == ["text", "json", "csv"]
    assert option.default == "text"
    assert option.show_default is True
    assert option.help == "Result format on stdout: text, json, csv."


def test_format_option_has_no_json_shorthand() -> None:
    """The --json shorthand was removed in 0.0.89; --format json replaces it."""
    result = CliRunner().invoke(_command(format_option()), ["--json"])
    assert result.exit_code == 2
    assert "No such option '--json'" in result.output
