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

import subprocess  # nosec B404
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((REPO_ROOT / "examples").glob("[0-9]*.py"))


def test_examples_discovered() -> None:
    """The glob must find the example scripts (guards against renames)."""
    assert len(EXAMPLES) >= 20


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
