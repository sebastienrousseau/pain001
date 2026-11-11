# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Keep the workflow audit's exceptions few, explained and harmless.

zizmor (.github/workflows/zizmor.yml) fails CI on any finding, so the
only way past it is an ignore. A reviewer reading the security evidence
reads those ignores, so each one sits inline on the line it excuses,
states its reason on that line, and never covers a class of risk that
must be fixed instead: template injection, a dangerous trigger, or a
token broader than the job needs. The configuration file holds policy
only, never an exception.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

IGNORE = re.compile(r"zizmor:\s*ignore\[([^\]]*)\](.*)$")
FORBIDDEN = {
    "template-injection",
    "dangerous-triggers",
    "excessive-permissions",
}
UNTRUSTED_TRIGGERS = {"pull_request_target", "workflow_run"}


def _workflows() -> list[Path]:
    return sorted((ROOT / ".github/workflows").glob("*.yml"))


def _audited_files() -> list[Path]:
    """Everything zizmor reads: workflows, actions, Dependabot, config."""
    files = [*_workflows(), *(ROOT / ".github/actions").glob("*/action.yml")]
    files += [ROOT / "action.yml", ROOT / ".github/dependabot.yml"]
    return [path for path in files if path.is_file()]


def _ignores() -> list[tuple[str, list[str], str]]:
    found = []
    for path in _audited_files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = IGNORE.search(line)
            if match:
                rules = [rule.strip() for rule in match.group(1).split(",")]
                where = f"{path.relative_to(ROOT)}:{number}"
                found.append((where, rules, match.group(2).strip()))
    return found


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def test_the_scan_finds_the_ignores_it_checks() -> None:
    """Guard against a pattern that silently matches nothing."""
    assert _ignores()


@pytest.mark.parametrize("where, rules, reason", _ignores())
def test_every_ignore_states_its_reason_on_its_line(
    where: str, rules: list[str], reason: str
) -> None:
    """An ignore without a reason is a finding nobody can review."""
    assert reason and not reason.startswith("#"), where
    assert len(reason.split()) >= 3, where


@pytest.mark.parametrize("where, rules, reason", _ignores())
def test_no_ignore_covers_a_risk_that_must_be_fixed(
    where: str, rules: list[str], reason: str
) -> None:
    """Injection, untrusted triggers and broad tokens are fixed, not ignored."""
    assert all(rules), where
    assert not FORBIDDEN & set(rules), where


def test_the_configuration_holds_policy_and_no_exception() -> None:
    """Exceptions live inline on one line each, never in .github/zizmor.yml."""
    config = _load(ROOT / ".github/zizmor.yml")
    for name, rule in config["rules"].items():
        assert set(rule) <= {"config"}, name
        assert "disable" not in rule and "ignore" not in rule, name
    policies = config["rules"]["unpinned-uses"]["config"]["policies"]
    assert policies == {"*": "hash-pin"}


@pytest.mark.parametrize("path", _workflows(), ids=lambda path: path.name)
def test_no_workflow_runs_on_an_untrusted_trigger(path: Path) -> None:
    """Neither trigger may run with this repository's trust on others' input."""
    events = _load(path)["on"]
    names = {events} if isinstance(events, str) else set(events)
    assert not UNTRUSTED_TRIGGERS & names


@pytest.mark.parametrize("path", _workflows(), ids=lambda path: path.name)
def test_workflow_level_permissions_grant_no_write(path: Path) -> None:
    """Every job inherits these, so writes are granted per job instead."""
    permissions = _load(path).get("permissions")
    assert isinstance(permissions, dict), path.name
    assert all(scope in {"read", "none"} for scope in permissions.values())


def _run_blocks(node: object) -> list[str]:
    if isinstance(node, dict):
        blocks = [node["run"]] if isinstance(node.get("run"), str) else []
        for value in node.values():
            blocks += _run_blocks(value)
        return blocks
    if isinstance(node, list):
        return [block for item in node for block in _run_blocks(item)]
    return []


@pytest.mark.parametrize(
    "path", _audited_files(), ids=lambda path: str(path.relative_to(ROOT))
)
def test_no_script_expands_a_template(path: Path) -> None:
    """Values reach a shell through env, never by expansion into its text."""
    for block in _run_blocks(_load(path)):
        assert "${{" not in block, path.name
