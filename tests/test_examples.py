# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""Run every script in examples/ and require a zero exit code.

Keeps the example suite honest: if the public API, CLI flags, or REST
routes change, the corresponding example fails in CI instead of
silently rotting.
"""

import re
import subprocess  # nosec B404
import sys
from pathlib import Path

import click
import pytest

import pain001
from pain001.cli.cli import cli

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((REPO_ROOT / "examples").glob("[0-9]*.py"))

#: Public names no example needs to show, each with the reason.
_API_NOT_DEMONSTRATED = {
    "__version__": "a constant, not a workflow",
    "main": "the CLI entry point; examples drive it as `pain001 ...`",
}
#: CLI commands no example runs, each with the reason.
_CLI_NOT_DEMONSTRATED = {
    "mcp": "blocks on stdio; 12_mcp_tools.py calls the same tools",
}


def _example_sources() -> str:
    """Return the text of every example script, concatenated."""
    return "\n".join(path.read_text(encoding="utf-8") for path in EXAMPLES)


def _cli_command_paths() -> list[tuple[str, ...]]:
    """Return every CLI command as its path of names from the root."""
    paths: list[tuple[str, ...]] = []
    for name, command in cli.commands.items():
        if isinstance(command, click.Group):
            paths.extend((name, sub) for sub in command.commands)
        else:
            paths.append((name,))
    return paths


def test_examples_discovered() -> None:
    """The glob must find the example scripts (guards against renames)."""
    assert len(EXAMPLES) >= 25


def test_every_public_name_has_an_example() -> None:
    """Every name in ``pain001.__all__`` is used by some example."""
    sources = _example_sources()
    missing = [
        name
        for name in pain001.__all__
        if name not in _API_NOT_DEMONSTRATED
        and not re.search(rf"\b{re.escape(name)}\b", sources)
    ]
    assert not missing, f"public API with no example: {missing}"


def test_every_cli_command_has_an_example() -> None:
    """Every CLI command and subcommand is run by some example."""
    missing = []
    for path in _cli_command_paths():
        if path[0] in _CLI_NOT_DEMONSTRATED:
            continue
        shown = any(
            all(
                re.search(rf"[\"']{re.escape(part)}[\"']", text)
                for part in path
            )
            for text in (p.read_text(encoding="utf-8") for p in EXAMPLES)
        )
        if not shown:
            missing.append(" ".join(path))
    assert not missing, f"CLI commands with no example: {missing}"


def test_exemptions_name_real_things() -> None:
    """An exemption for a removed name or command must be deleted."""
    assert set(_API_NOT_DEMONSTRATED) <= set(pain001.__all__)
    assert set(_CLI_NOT_DEMONSTRATED) <= set(cli.commands)


def test_every_example_is_documented() -> None:
    """A newly discovered workflow must have a runnable-guide entry."""
    guide = (REPO_ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    for example in EXAMPLES:
        assert f"`{example.name}`" in guide


@pytest.mark.parametrize(
    "benchmark_script",
    sorted((REPO_ROOT / "benches").glob("bench_*.py")),
    ids=lambda p: p.name,
)
def test_benchmark_smoke(benchmark_script: Path) -> None:
    """Every benchmark executes real work and its semantic assertions."""
    arguments = [sys.executable, str(benchmark_script)]
    if benchmark_script.name in {"bench_generate.py", "bench_corpus.py"}:
        arguments.append("--quick")
    result = subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, (
        f"{benchmark_script.name}:\n{result.stdout}\n{result.stderr}"
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_example_runs_cleanly(example: Path) -> None:
    """Each example exits 0 when run from the repository root."""
    result = subprocess.run(  # nosec B603
        [sys.executable, str(example)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        f"{example.name} failed with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
