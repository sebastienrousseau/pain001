# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Regression tests guarding the dependency-vulnerability gate migration (issue #175).

``safety check`` was deprecated in safety 2.x and removed in 3.x.
Safety 3 also gates ``safety scan`` behind an interactive login
prompt that hangs CI. v0.0.53 migrates the gate to ``pip-audit`` -
an actively-maintained, MIT-licensed equivalent with no auth and
already in use across the sibling packages (issue #175 explicitly
accepts ``or an equivalent supported scanner``).

These tests pin the new state in place so a careless revert can't
sneak back.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Tracked files where the active gate commands live. Markdown release
# notes and the policy header are allowed to mention the historical
# ``safety check`` form.
TRACKED_GATE_FILES = [
    ROOT / "Makefile",
    ROOT / ".github" / "workflows" / "security.yml",
    ROOT / "CONTRIBUTING.md",
    ROOT / ".github" / "copilot-instructions.md",
    ROOT / ".github" / "agents" / "python-deps.md",
    ROOT / ".github" / "agents" / "python-security.md",
    ROOT / ".github" / "agents" / "python-supply-chain.md",
]


@pytest.mark.parametrize("path", TRACKED_GATE_FILES, ids=lambda p: p.name)
def test_no_deprecated_safety_invocations(path: Path) -> None:
    """Active gate commands must not invoke the deprecated tooling.

    Criterion 6 of issue #175: no remaining ``safety check`` (v2,
    deprecated) or ``safety scan`` (v3, hangs in non-interactive CI)
    references in tracked files.
    """
    if not path.is_file():
        pytest.skip(f"{path} not present in this checkout")
    text = path.read_text(encoding="utf-8")
    assert "safety check" not in text, (
        f"{path.relative_to(ROOT)} still references deprecated "
        f"'safety check'; use 'pip-audit'."
    )
    assert "safety scan" not in text, (
        f"{path.relative_to(ROOT)} references 'safety scan' which "
        f"prompts for login in CI; use 'pip-audit' instead."
    )


def test_pip_audit_pin_present() -> None:
    """The ``pip-audit`` dev pin replaces ``safety``.

    Criterion 2 of issue #175: the dependency-scanner pin is raised
    to a version that supports non-interactive CI scanning.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(
        r'^pip-audit\s*=\s*"([^"]+)"', pyproject, re.MULTILINE
    )
    assert match, "pip-audit pin missing from pyproject.toml"
    pin = match.group(1)
    assert (
        ">=2" in pin or "^2" in pin or ">=3" in pin or "^3" in pin
    ), f"pip-audit pin {pin!r} does not require 2.x+"
    # Make sure the old safety pin is gone.
    assert not re.search(r'^safety\s*=', pyproject, re.MULTILINE), (
        "Replace `safety` with `pip-audit` in pyproject.toml"
    )


def test_makefile_sec_invokes_pip_audit() -> None:
    """The Makefile ``sec`` target must run ``pip-audit``.

    Criterion 1 of issue #175.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(
        r"^sec:.*?(?=^\S|\Z)", makefile, re.MULTILINE | re.DOTALL
    )
    assert match, "Makefile has no ``sec`` target"
    body = match.group(0)
    assert "pip-audit" in body, (
        "Makefile sec target must invoke pip-audit"
    )


def test_security_workflow_uses_pip_audit() -> None:
    """The ``Security`` workflow must invoke ``pip-audit``.

    Criteria 1 and 5 of issue #175: CI runs the scanner and saves a
    JSON report as an upload artifact.
    """
    workflow = (
        ROOT / ".github" / "workflows" / "security.yml"
    ).read_text(encoding="utf-8")
    assert "pip-audit" in workflow
    # Machine-readable artifact preserved.
    assert "pip-audit-report.json" in workflow
    # And one ``pip-audit`` line that actually gates the build
    # (does not swallow exit code via ``|| true``).
    has_gating_line = any(
        "pip-audit" in line and "|| true" not in line
        for line in workflow.splitlines()
    )
    assert has_gating_line, (
        "Security workflow has no failing-on-vuln pip-audit step"
    )


def test_safety_policy_kept_for_history_only() -> None:
    """The legacy ``.safety-policy.yml`` still ships for posterity.

    Criterion 3 of issue #175: the scoped, expiring ignore for the
    disputed CVE-2022-42969 is preserved. We keep the file even after
    moving off safety so the ignore reason survives in version control.
    """
    policy = (ROOT / ".safety-policy.yml").read_text(encoding="utf-8")
    assert "51457" in policy, "py CVE ignore (51457) is missing"
    assert "expires:" in policy, "policy ignore has no expiry"
