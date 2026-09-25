# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Time every numbered, self-checking example in a fresh interpreter.

These are end-to-end smoke timings including interpreter startup, not
microbenchmarks or service-level guarantees. Missing extras and failed
assertions must fail the run rather than silently removing a workload.
"""

import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def measure(example: Path) -> dict[str, object]:
    """Execute one real workflow, retaining failures and measuring elapsed time."""
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(example)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"{example.name} failed ({result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return {"example": example.name, "seconds": time.perf_counter() - started}


def main() -> None:
    """Discover all examples so additions cannot miss the benchmark inventory."""
    examples = sorted((ROOT / "examples").glob("[0-9]*.py"))
    if not examples:
        raise RuntimeError("No executable feature examples discovered")
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "timing_scope": "one fresh process per self-checking example",
                "samples": [measure(example) for example in examples],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
