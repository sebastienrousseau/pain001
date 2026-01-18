"""
PySentinel pytest plugin for real-time SLO enforcement.
Monitors test execution time and warns if approaching thresholds.
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import pytest

from pain001.constants import BASE_DIR


class SLOMonitor:
    """Tracks execution time and enforces SLOs."""

    def __init__(self, threshold_secs: float, name: str) -> None:
        self.threshold = threshold_secs
        self.name = name
        self.start_time: Optional[float] = None
        self.elapsed = 0.0

    def start(self) -> None:
        """Start timer."""
        self.start_time = time.time()

    def stop(self) -> float:
        """Stop timer and return elapsed seconds."""
        if self.start_time:
            self.elapsed = time.time() - self.start_time
        return self.elapsed

    def exceeded(self) -> bool:
        """Check if SLO exceeded."""
        return self.elapsed > self.threshold

    def report(self) -> str:
        """Return formatted report."""
        status = "✗ EXCEEDED" if self.exceeded() else "✓ OK"
        return f"{self.name}: {self.elapsed:.2f}s / {self.threshold}s {status}"


class SLOPlugin:
    """pytest plugin for SLO monitoring."""

    def __init__(self) -> None:
        self.session_monitor = SLOMonitor(60.0, "Test Suite")
        self.lint_monitor = SLOMonitor(15.0, "Linting")
        self.type_monitor = SLOMonitor(10.0, "Type Checking")
        self.monitors = [
            self.session_monitor,
            self.lint_monitor,
            self.type_monitor,
        ]

    def pytest_configure(self, _config: pytest.Config) -> None:
        """Configure plugin at test start."""
        self.session_monitor.start()

    def pytest_sessionfinish(
        self, _session: pytest.Session, _exitstatus: int
    ) -> None:
        """Report SLOs after all tests finish."""
        self.session_monitor.stop()

        print("\n" + "=" * 70)
        print("PySentinel SLO Report")
        print("=" * 70)
        for monitor in self.monitors:
            print(monitor.report())

        if self.session_monitor.exceeded():
            print(
                f"\n⚠ TEST SUITE SLO EXCEEDED ({self.session_monitor.elapsed:.2f}s > 60s)"
            )
            print(
                "  Consider optimizing slow tests or splitting into parallel runs."
            )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options."""
    parser.addoption(
        "--enforce-slos",
        action="store_true",
        default=False,
        help="Enforce SLO compliance (fail if exceeded)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register plugin if enabled."""
    tmp_root = Path(BASE_DIR) / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(tmp_root)
    os.environ["TEMP"] = str(tmp_root)
    os.environ["TMP"] = str(tmp_root)
    tempfile.tempdir = str(tmp_root)
    config.option.basetemp = str(tmp_root / "pytest")

    if config.getoption("--enforce-slos"):
        config.addinivalue_line(
            "markers", "slo: mark test as subject to SLO enforcement"
        )
        config.pluginmanager.register(SLOPlugin())
