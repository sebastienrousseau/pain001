# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Request-local custom rules gate both CLI and synchronous/async REST."""

import asyncio
import importlib
import sys
from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from pain001.api.app import _process_generation_job, app
from pain001.api.job_manager import JobStatus, job_manager
from pain001.api.models import GenerateXMLRequest
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR

_SOURCE = "pain001/templates/pain.001.001.03/template.csv"
_REJECT = '- id: POLICY-REJECT\n  where: "true"\n  severity: error\n  message: "Rejected by local policy."\n'
_ACCEPT = _REJECT.replace('"true"', '"false"')


@pytest.mark.parametrize("endpoint", ["/api/validate", "/api/generate"])
@pytest.mark.parametrize("rules,valid", [(_REJECT, False), (_ACCEPT, True)])
def test_rest_rules(endpoint, rules, valid):
    """Inline rules produce consistent results without writing a payment."""
    result = TestClient(app).post(
        endpoint,
        json={
            "file_path": _SOURCE,
            "data_source": "csv",
            "message_type": "pain.001.001.03",
            "rules": rules,
            "scheme": "sepa-sct,custom",
            "validate_only": True,
        },
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert (
        payload["is_valid" if endpoint.endswith("validate") else "success"]
        is valid
    )
    if not valid:
        assert payload["scheme_violations"][0]["rule"] == "POLICY-REJECT"


@pytest.mark.parametrize("endpoint", ["/api/validate", "/api/generate"])
def test_invalid_rest_rules(endpoint):
    """A malformed policy is a client error, never silently ignored."""
    response = TestClient(app).post(
        endpoint,
        json={
            "file_path": _SOURCE,
            "data_source": "csv",
            "message_type": "pain.001.001.03",
            "rules": "not a rule list",
        },
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "rules,expected",
    [(_REJECT, JobStatus.FAILED), (_ACCEPT, JobStatus.SUCCESS)],
)
def test_async_rules_never_bypass_gate(monkeypatch, rules, expected):
    """Background validation-only jobs enforce policy and never render XML."""
    module = importlib.import_module("pain001.api.app")
    generate = Mock(side_effect=AssertionError("must not render"))
    monkeypatch.setattr(module, "generate_xml", generate)
    request = GenerateXMLRequest(
        file_path=_SOURCE,
        data_source="csv",
        message_type="pain.001.001.03",
        rules=rules,
        validate_only=True,
    )
    job_id = job_manager.create_job()
    asyncio.run(_process_generation_job(job_id, request))
    assert job_manager.get_job(job_id).status == expected
    generate.assert_not_called()


@pytest.mark.parametrize("command", ["validate", "generate"])
@pytest.mark.parametrize("rules,exit_code", [(_REJECT, 1), (_ACCEPT, 0)])
def test_cli_policy(tmp_path, command, rules, exit_code):
    """Both CLI entry points forward the explicitly selected policy file."""
    policy = tmp_path / "rules.yaml"
    policy.write_text(rules, encoding="utf-8")
    args = [
        command,
        "-t",
        "pain.001.001.03",
        "-d",
        str(TEMPLATES_DIR / "pain.001.001.03/template.csv"),
        "--rules",
        str(policy),
    ]
    if command == "generate":
        args.append("--dry-run")
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == exit_code, result.output


def test_missing_rules_extra(monkeypatch):
    """Base installations give an actionable error without falling through."""
    monkeypatch.setitem(sys.modules, "pain001.validation.policy", None)
    response = TestClient(app).post(
        "/api/validate",
        json={
            "file_path": _SOURCE,
            "data_source": "csv",
            "message_type": "pain.001.001.03",
            "rules": _ACCEPT,
        },
    )
    assert response.status_code == 400
    assert "pain001[rules]" in response.text


def test_cli_missing_rules_extra(monkeypatch, tmp_path):
    """The CLI also refuses to skip a policy when its extra is absent."""
    monkeypatch.setitem(sys.modules, "pain001.validation.policy", None)
    rules = tmp_path / "rules.yaml"
    rules.write_text(_ACCEPT, encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        [
            "validate",
            "-t",
            "pain.001.001.03",
            "-d",
            _SOURCE,
            "--rules",
            str(rules),
        ],
    )
    assert result.exit_code == 2
    assert "pain001[rules]" in result.output
