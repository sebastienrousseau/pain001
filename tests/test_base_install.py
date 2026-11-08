# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The CLI works on a base install, with no optional extra.

``pip install pain001`` installs only the core dependencies, but the
test environment installs every extra, so an import of an optional
package on the CLI's start-up path passes here and breaks for users.
0.0.81 shipped one: ``pain001 --version`` raised ImportError without
the ``api`` extra. Each case runs in a subprocess whose import system
refuses every module an extra provides.
"""

from __future__ import annotations

import subprocess  # nosec B404
import sys
import textwrap
from pathlib import Path

import pytest

import pain001

# Top-level modules the optional extras provide (pyproject
# [tool.poetry.extras]), with what they pull in: fastapi brings
# starlette and pydantic.
EXTRAS_MODULES = (
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "pyarrow",
    "mcp",
    "pygls",
    "redis",
    "gnupg",
    "cryptography",
    "opentelemetry",
    "lxml",
    "paramiko",
    "celpy",
    "holidays",
)

SAMPLE = (
    Path(pain001.__file__).parent
    / "corpus"
    / "data"
    / "coverage"
    / "pain.001.001.09"
    / "01-transfer-every-element.xml"
)

_RUNNER = textwrap.dedent(
    """
    import sys

    BLOCKED = set(sys.argv[1].split(","))

    class Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in BLOCKED:
                raise ModuleNotFoundError(f"No module named {name!r}")
            return None

    sys.meta_path.insert(0, Block())
    from pain001.__main__ import cli

    cli(sys.argv[2:], prog_name="pain001")
    """
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        [sys.executable, "-c", _RUNNER, ",".join(EXTRAS_MODULES), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        ("--version",),
        ("--help",),
        ("check", "--help"),
        ("validate", "--help"),
        ("versions",),
    ],
    ids=lambda args: " ".join(args),
)
def test_the_cli_starts_without_any_extra(args: tuple[str, ...]) -> None:
    result = _run(*args)
    assert result.returncode == 0, result.stderr


def test_check_runs_without_any_extra() -> None:
    result = _run("check", str(SAMPLE))
    assert result.returncode == 0, result.stderr
    assert "pain.001.001.09 passed" in result.stdout


def test_the_blocker_really_blocks() -> None:
    """Without this, every case above could pass vacuously."""
    probe = subprocess.run(  # nosec B603
        [
            sys.executable,
            "-c",
            _RUNNER.replace(
                "from pain001.__main__ import cli", "import fastapi"
            ),
            "fastapi",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert probe.returncode != 0
    assert "No module named 'fastapi'" in probe.stderr
