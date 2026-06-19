# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    assert len(EXAMPLES) >= 14


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_example_runs_cleanly(example: Path) -> None:
    """Each example exits 0 when run from the repository root."""
    if "api" in example.name:
        pytest.importorskip("fastapi")
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
