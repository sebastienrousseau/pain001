# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The GitHub Action and the pre-commit hooks stay in step with the CLI.

``action.yml`` and ``.pre-commit-hooks.yaml`` call ``pain001 check`` and
``pain001 validate`` by name and flag; a renamed command or option
would break every repository that uses them without failing a test
here. Each is also pinned and wired as the repository's own workflows
are.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import click
import pytest
import yaml

from pain001.cli.cli import cli

ROOT = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
HOOKS = yaml.safe_load(
    (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
)


def _options(command: str) -> set[str]:
    group = cli
    assert isinstance(group, click.Group)
    found = group.commands[command]
    return {opt for param in found.params for opt in param.opts}


def _steps() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = ACTION["runs"]["steps"]
    return steps


def test_the_action_is_a_composite_with_pinned_actions() -> None:
    assert ACTION["runs"]["using"] == "composite"
    for step in _steps():
        if "uses" in step:
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), step


def test_every_input_the_action_reads_is_declared() -> None:
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    used = set(re.findall(r"inputs\.([\w-]+)", text))
    assert used <= set(ACTION["inputs"]), used - set(ACTION["inputs"])


def test_the_action_passes_only_real_check_options() -> None:
    script = next(s["run"] for s in _steps() if s.get("id") == "check")
    flags = set(re.findall(r"(?<![\w-])(--[a-z][\w-]*|-o)\b", script))
    assert flags <= _options("check"), flags - _options("check")


def test_the_action_installs_its_own_checkout() -> None:
    install = next(
        s["run"] for s in _steps() if s["name"].startswith("Install pain001")
    )
    assert "pip install" in install
    assert "$ACTION_PATH" in install


@pytest.mark.parametrize("hook", HOOKS, ids=[hook["id"] for hook in HOOKS])
def test_each_hook_runs_a_real_command_and_options(
    hook: dict[str, Any],
) -> None:
    program, command, *flags = hook["entry"].split()
    assert program == "pain001"
    assert command in cli.commands  # type: ignore[attr-defined]
    assert set(flags) <= _options(command)
    assert hook["language"] == "python"


def test_the_check_hook_skips_unrelated_xml() -> None:
    (check,) = (hook for hook in HOOKS if hook["id"] == "pain001-check")
    assert "--skip-other-xml" in check["entry"]
    assert check["types"] == ["xml"]
