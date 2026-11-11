# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""User-controlled text never reaches Rich as markup.

The CLI prints through a Rich console with markup on. A file name, a
data value, a plugin's metadata or an exception message that contains
``[/x]`` used to end the run in ``rich.errors.MarkupError`` with a
traceback; ``[bold]`` or ``[link=...]`` was silently swallowed or
turned into a live terminal hyperlink. Each test feeds one of those
payloads through a print site and checks the text comes out literally.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner, Result

from pain001 import __main__ as entry
from pain001.cli import _generate_steps as steps
from pain001.cli._format import Reporter
from pain001.cli._gpg import _apply_gpg_options
from pain001.cli.cli import cli
from pain001.plugins import PAIN001_API_VERSION, PluginInfo, PluginMeta
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation._scheme_types import SchemeValidationResult

MTYPE = "pain.001.001.03"
PAYLOADS = [
    "[/x]",
    "[bold]bold[/bold]",
    "[link=https://evil.example]click[/link]",
]
TEMPLATE = DEFAULT_TEMPLATE_REGISTRY.get_template(MTYPE)
SAMPLE_CSV = Path(TEMPLATE.template_path).parent / "template.csv"


def _flat(text: str) -> str:
    """Join Rich's soft-wrapped lines so a long literal stays whole."""
    return text.replace("\n", "")


def _assert_literal(result: Result, payload: str) -> None:
    """The run ended normally and printed ``payload`` verbatim."""
    assert result.exception is None or isinstance(
        result.exception, SystemExit
    ), repr(result.exception)
    assert payload in _flat(result.output)


@pytest.fixture
def runner(monkeypatch, tmp_path) -> CliRunner:
    """A CLI runner working in an empty directory, so paths stay short."""
    monkeypatch.chdir(tmp_path)
    shutil.copyfile(SAMPLE_CSV, tmp_path / "rows.csv")
    return CliRunner()


@pytest.mark.parametrize("payload", PAYLOADS)
def test_missing_data_file_name(runner, payload):
    """The reported crash: a data path holding markup in an error."""
    name = f"pay{payload}.csv"
    result = runner.invoke(cli, ["generate", "-t", MTYPE, "-d", name])
    _assert_literal(result, name)
    assert result.exit_code == 2


@pytest.mark.parametrize("payload", PAYLOADS)
def test_output_dir_and_success_message(runner, payload):
    """The output directory is echoed on start and on success."""
    with patch.object(steps, "process_files"):
        result = runner.invoke(
            cli,
            ["generate", "-t", MTYPE, "-d", "rows.csv", "-o", payload],
        )
    _assert_literal(result, payload)
    assert result.exit_code == 0


@pytest.mark.parametrize("payload", PAYLOADS)
def test_generation_failure_and_traceback(runner, payload):
    """An exception message, and its verbose traceback, print literally."""
    with patch.object(steps, "process_files", side_effect=ValueError(payload)):
        result = runner.invoke(
            cli,
            ["generate", "-t", MTYPE, "-d", "rows.csv", "--verbose"],
        )
    _assert_literal(result, f"Generation failed: {payload}")
    assert f"ValueError: {payload}" in _flat(result.output)
    assert result.exit_code == 1


@pytest.mark.parametrize("payload", PAYLOADS)
def test_schematron_report_and_name(runner, payload):
    """A Schematron rulebook name and its report print literally."""
    report = MagicMock(is_valid=False)
    report.format_report.return_value = f"rule broke: {payload}"
    with (
        patch("pain001.schematron.validate_schematron", return_value=report),
        patch(
            "pain001.xml.generate_xml.generate_xml_string",
            return_value="<x/>",
        ),
    ):
        result = runner.invoke(
            cli,
            [
                "validate",
                "-t",
                MTYPE,
                "-d",
                "rows.csv",
                "--schematron",
                f"r{payload}.sch",
            ],
        )
    _assert_literal(result, f"rule broke: {payload}")
    assert f"r{payload}.sch" in _flat(result.output)
    assert result.exit_code == 1

    report.is_valid = True
    report.rules_passed = report.rules_evaluated = 1
    with (
        patch("pain001.schematron.validate_schematron", return_value=report),
        patch(
            "pain001.xml.generate_xml.generate_xml_string",
            return_value="<x/>",
        ),
    ):
        result = runner.invoke(
            cli,
            [
                "validate",
                "-t",
                MTYPE,
                "-d",
                "rows.csv",
                "--schematron",
                f"r{payload}.sch",
            ],
        )
    _assert_literal(result, f"r{payload}.sch' passed")
    assert result.exit_code == 0


def _violation(payload: str, severity: str) -> MagicMock:
    """A scheme violation whose every text field carries ``payload``."""
    return MagicMock(
        rule=f"rule{payload}",
        message=f"msg{payload}",
        index=0,
        field=f"field{payload}",
        severity=severity,
        remediation=f"fix{payload}",
    )


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("severity", ["warning", "error"])
def test_scheme_violation_text(capsys, payload, severity):
    """Violation rule, field, message and remediation print literally."""
    result = SchemeValidationResult(
        profile="custom", violations=[_violation(payload, severity)]
    )
    opts = {
        "scheme": f"s{payload}",
        "rules": None,
        "explain": True,
        "scheme_format": "text",
        "xml_message_type": MTYPE,
    }
    with patch.object(steps, "validate_scheme", return_value=result):
        try:
            steps.run_scheme_check(Reporter(), steps.Outcome(), [], opts)
        except SystemExit as exc:
            assert severity == "error" and exc.code == 1
    out = _flat(capsys.readouterr().err)
    for text in ("rule", "msg", "field", "fix", "s"):
        assert f"{text}{payload}" in out
    assert f"[rule{payload}]" in out


@pytest.mark.parametrize("payload", PAYLOADS)
def test_gpg_key_file_and_metrics(capsys, monkeypatch, payload):
    """The GPG key path and metric attributes print literally."""
    # setenv records the original state, so the value the CLI writes
    # is rolled back and cannot leak into the GPG tests.
    monkeypatch.setenv("PAIN001_GPG_KEYFILE", "")
    _apply_gpg_options(f"k{payload}.asc", None)
    event = MagicMock(timestamp=0.0, trace_context={})
    event.name = "evt"
    event.attributes = {"path": payload}
    steps.emit_metric(event)
    captured = capsys.readouterr()
    assert f"k{payload}.asc" in _flat(captured.err)
    assert json.loads(captured.out)["attributes"] == {"path": payload}


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("command", ["inspect", "init"])
def test_unknown_message_type_argument(runner, command, payload):
    """``inspect`` and ``init`` echo an unknown type literally."""
    result = runner.invoke(cli, [command, f"t{payload}"])
    _assert_literal(result, f"t{payload}")
    assert result.exit_code == 2


@pytest.mark.parametrize("payload", PAYLOADS)
def test_init_destination(runner, payload):
    """``init`` names the file it wrote literally."""
    target = Path(f"out{payload}.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    result = runner.invoke(cli, ["init", MTYPE, "-o", str(target)])
    _assert_literal(result, str(target))
    assert result.exit_code == 0


@pytest.mark.parametrize("payload", PAYLOADS)
def test_inspect_template_paths(runner, payload):
    """Template details print their paths literally."""
    meta = dataclasses.replace(
        TEMPLATE,
        template_path=Path(f"t{payload}.xml"),
        example_data_path=Path(f"d{payload}.csv"),
        example_xml_path=Path(f"x{payload}.xml"),
    )
    with patch.object(
        DEFAULT_TEMPLATE_REGISTRY, "get_template", return_value=meta
    ):
        result = runner.invoke(cli, ["inspect", MTYPE])
    for name in ("t{}.xml", "d{}.csv", "x{}.xml"):
        _assert_literal(result, str(Path(name.format(payload))))


def _info(payload: str) -> PluginInfo:
    """A plugin record whose third-party metadata carries ``payload``."""
    return PluginInfo(
        kind="loader",
        meta=PluginMeta(
            name=f"n{payload}",
            version="1.0.0",
            description=f"desc{payload}",
            api_version=PAIN001_API_VERSION,
            source=f"src{payload}",
        ),
    )


@pytest.mark.parametrize("payload", PAYLOADS)
def test_plugin_metadata(runner, payload):
    """Plugin names, sources and descriptions print literally."""
    from pain001.plugins.registry import registry as plugin_registry

    with patch.object(
        plugin_registry, "list_plugins", return_value=[_info(payload)]
    ):
        shown = runner.invoke(cli, ["plugins", "show", f"n{payload}"])
        missing = runner.invoke(
            cli, ["plugins", "show", f"m{payload}", "--kind", "loader"]
        )
    for text in ("n", "src", "desc"):
        _assert_literal(shown, f"{text}{payload}")
    _assert_literal(missing, f"m{payload}")
    assert missing.exit_code == 1


def test_plugin_table_cells(runner):
    """Table cells are markup too; a closing tag must not crash them."""
    from pain001.plugins.registry import registry as plugin_registry

    with patch.object(
        plugin_registry, "list_plugins", return_value=[_info("[/x]")]
    ):
        result = runner.invoke(cli, ["plugins", "list"])
    assert result.exception is None, repr(result.exception)
    assert "[/x]" in result.output


@pytest.mark.parametrize("payload", PAYLOADS)
def test_serve_host(runner, payload):
    """The bind address printed by ``serve`` is literal."""
    pytest.importorskip("uvicorn")
    with (
        patch("uvicorn.run"),
        patch("pain001.cli._serve.init_otel"),
    ):
        # A non-loopback host needs a key since D9 (ADR 0009).
        result = runner.invoke(
            cli,
            ["serve", "--host", f"h{payload}"],
            env={"PAIN001_API_KEY": "test-key"},
        )
    _assert_literal(result, f"h{payload}")


@pytest.mark.parametrize("payload", PAYLOADS)
def test_python_m_entry_errors(capsys, tmp_path, payload):
    """``python -m pain001`` prints report errors and exceptions literally."""
    data = tmp_path / "rows.csv"
    shutil.copyfile(SAMPLE_CSV, data)
    report = MagicMock(is_valid=False, errors=[f"bad{payload}"])
    service = MagicMock()
    service.validate_all.return_value = report
    args = (MTYPE, str(TEMPLATE.template_path), str(TEMPLATE.xsd_path))
    with (
        patch.object(entry, "ValidationService", return_value=service),
        pytest.raises(SystemExit),
    ):
        entry.main(*args, str(data))
    assert f"bad{payload}" in _flat(capsys.readouterr().out)

    report.is_valid = True
    with (
        patch.object(entry, "ValidationService", return_value=service),
        patch.object(entry, "process_files", side_effect=OSError(payload)),
        pytest.raises(SystemExit),
    ):
        entry.main(*args, str(data))
    assert f"An error occurred: {payload}" in _flat(capsys.readouterr().out)
