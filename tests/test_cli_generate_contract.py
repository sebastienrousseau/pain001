# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Pin what ``generate`` resolves, reports and logs, value by value.

The command-line tests check that a bad configuration or a missing
option fails, mostly with ``in``; they do not pin the exact message,
the fields of the ``cli_args_parsed`` event, or which object the
validation step receives, so the mutation run's survivors in
``_resolve_config``, ``_resolve``, ``_pipeline``,
``_require_message_type`` and ``DefaultGroup.parse_args`` were only
killed incidentally. These tests call the helpers with spies in place
of the steps around them and compare exactly.
"""

from __future__ import annotations

import io
import logging
from typing import Any, cast

import click
import pytest
import yaml
from click.testing import CliRunner
from rich.console import Console

from pain001.cli import _generate
from pain001.cli._config import _resolve_config
from pain001.cli._format import Failure, Reporter
from pain001.cli._generate_steps import Outcome
from pain001.cli._paths import _require_message_type
from pain001.cli.cli import cli
from pain001.config import ConfigManager
from pain001.constants import valid_xml_types
from pain001.logging_schema import Events

MTYPE = "pain.001.001.09"
LOGGER = logging.getLogger("pain001.tests.generate_contract")


class _Raising:
    """A configuration manager whose ``resolve`` raises ``exc``."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def resolve(self, _args: dict[str, Any]) -> dict[str, Any]:
        """Raise the configured exception."""
        raise self.exc


def _config_error(exc: Exception, **args: Any) -> str:
    """The usage-error message ``_resolve_config`` turns ``exc`` into."""
    with pytest.raises(click.UsageError) as caught:
        _resolve_config(args, cast(ConfigManager, _Raising(exc)))
    return caught.value.message


def test_yaml_error_without_a_file_name() -> None:
    """With no ``config_file`` the message names the file generically."""
    assert _config_error(yaml.YAMLError("bad")) == (
        "the configuration file is not valid YAML: bad"
    )


def test_key_error_reports_its_argument_unquoted() -> None:
    """A ``KeyError`` reports its argument, not its quoted repr."""
    assert _config_error(KeyError("Unknown profile: x")) == (
        "Unknown profile: x"
    )


def test_error_without_arguments_is_empty() -> None:
    """An exception with no arguments gives an empty message."""
    assert _config_error(ValueError()) == ""


def _recording_reporter() -> Reporter:
    """A reporter whose console records what it prints."""
    console = Console(record=True, width=10_000, file=io.StringIO())
    return Reporter(console=console)


def test_unknown_message_type_is_exact() -> None:
    """The console line and the failure message are exact."""
    rep = _recording_reporter()
    with pytest.raises(Failure) as caught:
        _require_message_type(rep.console, "pain.999")
    assert caught.value.message == "Invalid XML message type: pain.999"
    assert rep.console.export_text() == (
        "✗ Error: Invalid XML message type: pain.999\n"
        f"Valid types: {', '.join(valid_xml_types)}\n"
    )


def _opts(**given: Any) -> dict[str, Any]:
    """Every option ``_resolve`` and ``_pipeline`` read, empty."""
    keys = (*_generate._CONFIG_KEYS, "show_config", "dry_run", "rules")
    opts: dict[str, Any] = dict.fromkeys(keys)
    opts.update(scheme=None, **given)
    return opts


@pytest.mark.parametrize(
    ("resolved", "label"),
    [
        ({}, "XML message type"),
        ({"xml_message_type": MTYPE}, "data file path"),
    ],
)
def test_missing_option_is_exact(
    monkeypatch: pytest.MonkeyPatch, resolved: dict[str, Any], label: str
) -> None:
    """A missing message type or data file is named exactly."""
    monkeypatch.setattr(_generate, "_resolve_config", lambda _: resolved)
    rep = _recording_reporter()
    with pytest.raises(Failure) as caught:
        _generate._resolve(rep, _opts())
    assert caught.value.message == f"Missing {label}"
    assert rep.console.export_text() == f"✗ Error: Missing {label}\n"


def _stub_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, list[Any]]:
    """Replace every step around ``_pipeline``; return their calls."""
    calls: dict[str, list[Any]] = {"log": [], "validate": [], "gen": []}
    monkeypatch.setattr(_generate, "_resolve", lambda *_: {})
    monkeypatch.setattr(_generate, "_prepare", lambda *_: None)
    monkeypatch.setattr(
        _generate,
        "log_event",
        lambda _logger, level, event, **fields: calls["log"].append(
            (level, event, fields)
        ),
    )
    monkeypatch.setattr(
        _generate,
        "validate_data",
        lambda _rep, outcome, *_: calls["validate"].append(outcome),
    )
    monkeypatch.setattr(
        _generate,
        "generate_files",
        lambda _rep, outcome, _opts: calls["gen"].append(outcome),
    )
    return calls


def test_pipeline_records_inputs_and_logs_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outcome names the data file; the event carries both fields."""
    calls = _stub_pipeline(monkeypatch)
    opts = _opts(xml_message_type=MTYPE, data_file_path="pay.csv")
    opts.update(dry_run=False, scheme="sepa")
    outcome = Outcome()
    assert _generate._pipeline(Reporter(), outcome, opts, LOGGER) is True
    assert outcome.data_file == "pay.csv"
    assert outcome.message_type == MTYPE
    assert calls["log"] == [
        (
            logging.INFO,
            Events.CLI_ARGS_PARSED,
            {"message_type": MTYPE, "dry_run": False},
        )
    ]
    assert calls["validate"] == [outcome]
    assert calls["validate"][0] is outcome
    assert calls["gen"][0] is outcome


@pytest.mark.parametrize("flag", ["-h", "-V"])
def test_short_group_flags_are_not_routed(flag: str) -> None:
    """``-h`` and ``-V`` belong to the group, as their long forms do."""
    long_form = {"-h": "--help", "-V": "--version"}[flag]
    short = CliRunner().invoke(cli, [flag])
    full = CliRunner().invoke(cli, [long_form])
    assert short.exit_code == 0
    assert short.output == full.output


def test_lower_case_v_is_routed_to_generate() -> None:
    """``-v`` is ``generate``'s ``--verbose``, not the group's version."""
    result = CliRunner().invoke(cli, ["-v", "--list-templates"])
    version = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output != version.output
