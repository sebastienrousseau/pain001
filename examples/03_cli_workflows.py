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

"""Drive the ``pain001`` CLI end to end and check its exit codes.

Demonstrates the documented contract:

* ``0`` — success (dry-run validation and XML generation)
* ``2`` — invalid arguments (unknown message type)

The working files are copied into a temporary directory first, so the
generated XML lands next to the copied template instead of inside the
installed package.

Run from the repository root::

    python examples/03_cli_workflows.py
"""

import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from pain001.constants import TEMPLATES_DIR

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the pain001 CLI in a subprocess and return the result.

    Args:
        args: CLI arguments to append after ``python -m pain001``.
        cwd: Working directory for the subprocess.

    Returns:
        The completed process with captured output.
    """
    return subprocess.run(  # nosec B603
        [sys.executable, "-m", "pain001", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def main() -> None:
    """Exercise dry-run, generation, and argument-error exit codes."""
    template_dir = TEMPLATES_DIR / MESSAGE_TYPE

    with tempfile.TemporaryDirectory() as workdir_str:
        workdir = Path(workdir_str)
        shutil.copy(template_dir / "template.xml", workdir)
        shutil.copy(template_dir / f"{MESSAGE_TYPE}.xsd", workdir)
        shutil.copy(DATA_FILE, workdir / "payments.csv")

        common = [
            "-t",
            MESSAGE_TYPE,
            "-m",
            "template.xml",
            "-s",
            f"{MESSAGE_TYPE}.xsd",
            "-d",
            "payments.csv",
        ]

        result = run_cli([*common, "--dry-run"], cwd=workdir)
        assert result.returncode == 0, result.stdout + result.stderr
        print("dry-run            -> exit 0 (validation only, no XML)")

        result = run_cli(common, cwd=workdir)
        assert result.returncode == 0, result.stdout + result.stderr
        output_file = workdir / f"{MESSAGE_TYPE}.xml"
        assert output_file.exists(), "expected XML next to the template"
        print(
            f"generate           -> exit 0 "
            f"({output_file.name}, {output_file.stat().st_size} bytes)"
        )

        result = run_cli(
            ["-t", "pain.999.999.99", "-d", "payments.csv"], cwd=workdir
        )
        assert result.returncode == 2, result.stdout + result.stderr
        print("bad message type   -> exit 2 (invalid arguments)")


if __name__ == "__main__":
    main()
