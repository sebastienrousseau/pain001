# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Regression tests guarding the Safety CLI migration (issue #175).

``safety check`` was deprecated upstream and removed in safety 3.x.
v0.0.53 migrates the dependency gate to ``safety scan``. These tests
pin the new state in place so a careless revert can't sneak back.
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
def test_no_safety_check_in_tracked_gate_files(path: Path) -> None:
    """Active gate commands must use ``safety scan``, not ``safety check``.

    Criterion 6 of issue #175: a docs regression check asserts no
    remaining ``safety check`` references in tracked files.
    """
    if not path.is_file():
        pytest.skip(f"{path} not present in this checkout")
    text = path.read_text(encoding="utf-8")
    assert "safety check" not in text, (
        f"{path.relative_to(ROOT)} still references deprecated "
        f"'safety check'; use 'safety scan'."
    )


def test_safety_pin_supports_scan_command() -> None:
    """The ``safety`` dev dep pin must be a version exposing ``scan``.

    Criterion 2 of issue #175: the safety dev-dependency pin is raised
    to a version supporting ``scan``. ``safety scan`` was introduced in
    3.x; anything below that ships only ``check``.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^safety\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match, "safety pin missing from pyproject.toml"
    pin = match.group(1)
    # Accept either ">=3.x,<Y" or "^3.x" style. Reject anything starting
    # at ^2 or <3.
    assert (
        ">=3" in pin or "^3" in pin or ">=4" in pin or "^4" in pin
    ), f"safety pin {pin!r} does not require 3.x+"


def test_makefile_sec_invokes_safety_scan() -> None:
    """The Makefile ``sec`` target must run ``safety scan``.

    Criterion 1 of issue #175.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    # Find the ``sec:`` recipe body.
    match = re.search(
        r"^sec:.*?(?=^\S|\Z)", makefile, re.MULTILINE | re.DOTALL
    )
    assert match, "Makefile has no ``sec`` target"
    body = match.group(0)
    assert "safety scan" in body, (
        "Makefile sec target must invoke safety scan"
    )


def test_security_workflow_uses_safety_scan() -> None:
    """The ``Security`` workflow must invoke ``safety scan``.

    Criterion 1 and 5 of issue #175: CI runs ``safety scan`` and the
    JSON report becomes an upload artifact.
    """
    workflow = (
        ROOT / ".github" / "workflows" / "security.yml"
    ).read_text(encoding="utf-8")
    assert "safety scan" in workflow
    # JSON output artifact is preserved.
    assert "safety-report.json" in workflow
    # And it actually gates the build (the second ``safety scan`` line
    # that does NOT swallow exit code via ``|| true``).
    has_gating_line = any(
        "safety scan" in line and "|| true" not in line
        for line in workflow.splitlines()
    )
    assert has_gating_line, (
        "Security workflow has no failing-on-vuln safety scan step"
    )


def test_safety_policy_ignore_is_preserved() -> None:
    """The disputed ``py`` CVE ignore is preserved across the migration.

    Criterion 3 of issue #175: the scoped, expiring ignore is preserved.
    """
    policy = (ROOT / ".safety-policy.yml").read_text(encoding="utf-8")
    assert "51457" in policy, "py CVE ignore (51457) is missing"
    assert "expires:" in policy, "policy ignore has no expiry"
