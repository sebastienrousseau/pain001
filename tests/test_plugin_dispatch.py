# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Installed plugins must affect execution, not just registry inspection."""

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.data.loader import load_payment_data, load_payment_data_streaming
from pain001.exceptions import DataSourceError
from pain001.plugins import (
    LoaderResult,
    PluginMeta,
    SchemeFinding,
    SchemeResult,
    ValidatorFinding,
    ValidatorResult,
)
from pain001.plugins.registry import PluginRegistry
from pain001.validation.schema_validator import SchemaValidator
from pain001.validation.schemes import validate_scheme


@pytest.fixture
def registry(monkeypatch):
    """Use real built-ins but isolate registrations from other tests."""
    module = importlib.import_module("pain001.plugins.registry")
    monkeypatch.setattr(module, "_load_entry_point_plugins", lambda reg: None)
    isolated = PluginRegistry((0, 54))
    isolated.list_plugins()
    monkeypatch.setattr(module, "registry", isolated)
    return isolated


@pytest.mark.parametrize("extension", [".csv", ".CSV", ".custom"])
def test_loader_override_and_streaming(
    registry, monkeypatch, tmp_path, extension
):
    """Whole-file and streaming paths select the same installed loader."""
    target = tmp_path / ("records" + extension)
    target.write_text("synthetic", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "pain001.data.loader.validate_csv_data", lambda rows: True
    )
    result = LoaderResult(rows=[{"from_plugin": True}])
    loader = SimpleNamespace(
        meta=PluginMeta("csv", "0.0.1", "Override", source="test==0.0.1"),
        extensions=(".csv", ".custom"),
        load=Mock(return_value=result),
        load_streaming=Mock(return_value=[result]),
    )
    registry.register_loader(loader)
    assert load_payment_data(str(target)) == result.rows
    assert list(load_payment_data_streaming(str(target), chunk_size=1)) == [
        result.rows
    ]
    loader.load.assert_called_once_with(str(target))
    loader.load_streaming.assert_called_once_with(str(target), 1)


def test_disabled_loader_is_not_bypassed(registry, monkeypatch, tmp_path):
    """Removing a built-in disables execution as well as listing."""
    monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", "csv")
    registry.reset()
    with pytest.raises(DataSourceError):
        load_payment_data(str(tmp_path / "unread.csv"))


@pytest.mark.parametrize("name", ["sepa-sct", "local-scheme"])
def test_scheme_dispatch_preserves_message_type(registry, name):
    """Overrides and new profile names both participate in validation."""
    finding = SchemeFinding(
        0, "debtor_name", "LOCAL", "error", "Review this name."
    )
    plugin = SimpleNamespace(
        meta=PluginMeta(name, "0.0.1", "Local"),
        validate=Mock(return_value=SchemeResult(False, [finding])),
    )
    registry.register_scheme(plugin)
    rows = [{}]
    result = validate_scheme(rows, name, message_type="pain.001.001.09")
    assert result.is_valid is False
    assert result.violations[0].rule == "LOCAL"
    plugin.validate.assert_called_once_with(
        rows, message_type="pain.001.001.09"
    )


@pytest.mark.parametrize("enabled", [True, False])
def test_writer_dispatch(registry, monkeypatch, tmp_path, enabled):
    """Writer overrides receive the rendered bytes verbatim; disabled fails."""
    module = importlib.import_module("pain001.xml.generate_xml")
    monkeypatch.setattr(
        module, "generate_xml_string", lambda *args: "<synthetic/>\n"
    )
    target = tmp_path / "payment.xml"
    writer = SimpleNamespace(
        meta=PluginMeta("xml-file", "0.0.1", "Writer"),
        write=Mock(return_value=str(target)),
    )
    if enabled:
        registry.register_writer(writer)
        assert module.generate_xml(
            [], "pain.001.001.03", "unused", "unused", str(target)
        ) == str(target)
        writer.write.assert_called_once_with("<synthetic/>\n", str(target))
    else:
        monkeypatch.setenv("PAIN001_DISABLE_PLUGINS", "xml-file")
        registry.reset()
        with pytest.raises(ValueError, match="disabled"):
            module.generate_xml(
                [], "pain.001.001.03", "unused", "unused", str(target)
            )
    assert not target.exists()


@pytest.mark.parametrize(
    "severity,field",
    [("error", "debtor_name"), ("error", None), ("warning", None)],
)
def test_validator_dispatch(registry, monkeypatch, severity, field):
    """Plugin errors augment schema results without duplicating bad rows."""
    validator = SchemaValidator("pain.001.001.03")
    monkeypatch.setattr(validator, "validate_data", lambda row: [])
    result = ValidatorResult(
        severity != "error",
        [ValidatorFinding(0, field, "LOCAL", severity, "Review.")],
    )
    plugin = SimpleNamespace(
        meta=PluginMeta("local", "0.0.1", "Local"),
        validate=Mock(return_value=result),
    )
    registry.register_validator(plugin)
    total, valid, errors = validator.validate_batch([{}])
    assert total == 1
    assert valid == (0 if severity == "error" else 1)
    if errors:
        assert errors[0][1][0].rule == "LOCAL"
        assert errors[0][1][0].value is None


@pytest.mark.parametrize(
    "result",
    [
        ValidatorResult(False, []),
        ValidatorResult(
            True, [ValidatorFinding(2, None, "LOCAL", "warning", "Review.")]
        ),
    ],
)
def test_invalid_validator_result_is_refused(registry, monkeypatch, result):
    """A malformed plugin report cannot silently validate payment rows."""
    validator = SchemaValidator("pain.001.001.03")
    monkeypatch.setattr(validator, "validate_data", lambda row: [])
    registry.register_validator(
        SimpleNamespace(
            meta=PluginMeta("local", "0.0.1", "Local"),
            validate=lambda *a, **kw: result,
        )
    )
    with pytest.raises(ValueError, match="Validator plugin"):
        validator.validate_batch([{}])


def test_validator_registry_change_fails_closed(registry, monkeypatch):
    """Concurrent registry mutation cannot silently bypass a validator."""
    registry.register_validator(
        SimpleNamespace(meta=PluginMeta("local", "0.0.1", "Local"))
    )
    monkeypatch.setattr(registry, "get_validator", lambda name: None)
    with pytest.raises(ValueError, match="registry changed"):
        SchemaValidator("pain.001.001.03").validate_batch([])


@pytest.mark.parametrize("name,code", [("xlsx", 0), ("a; command", 2)])
def test_disable_name_is_shell_safe(name, code):
    """The escape-hatch command prints instructions without modifying state."""
    result = CliRunner().invoke(cli, ["plugins", "disable", name])
    assert result.exit_code == code
    if code == 0:
        assert "export PAIN001_DISABLE_PLUGINS=xlsx" in result.output
        assert "no settings were changed" in result.output
