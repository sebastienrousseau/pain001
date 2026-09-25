# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Release risk acceptances cannot silently become permanent suppressions."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("today", "returncode"),
    [
        ("2026-09-25", 0),
        ("2026-10-24", 0),
        ("2026-10-25", 1),
        ("2026-12-24", 1),
        ("2026-09-24", 1),
    ],
)
def test_review_and_expiry_deadlines(today: str, returncode: int) -> None:
    """Review is blocking on its due date, not just after final expiry."""
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_security_exceptions.py"),
            "--today",
            today,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == returncode, result.stderr


@pytest.mark.parametrize(
    "mutation", ["empty", "duplicate", "owner", "date", "missing"]
)
def test_malformed_registry_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    """Missing ownership, malformed dates and duplicate acceptances are errors."""
    data = json.loads((ROOT / "docs/security-exceptions.json").read_text())
    entry = data["exceptions"][0]
    if mutation == "empty":
        data["exceptions"] = []
    elif mutation == "duplicate":
        entry["alerts"].append(entry["alerts"][0])
    elif mutation == "owner":
        entry["owner"] = ""
    elif mutation == "date":
        entry["expires"] = "invalid"
    else:
        del entry["controls"]
    registry = tmp_path / "exceptions.json"
    registry.write_text(json.dumps(data))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_security_exceptions.py"),
            "--registry",
            str(registry),
            "--today",
            "2026-09-25",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "gate failed" in result.stderr
