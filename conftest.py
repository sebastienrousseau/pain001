"""
PySentinel pytest plugin for real-time SLO enforcement.
Monitors test execution time and warns if approaching thresholds.
"""

import os
import tempfile
import time
from pathlib import Path

import pytest

from pain001.constants import BASE_DIR

# Starlette's TestClient addresses the app as "testserver". A REST
# server without PAIN001_API_KEY answers only loopback hosts, plus the
# ones PAIN001_ALLOWED_HOSTS names, so the suite names its client here;
# tests/test_api_host_guard.py clears it to test the default.
os.environ.setdefault("PAIN001_ALLOWED_HOSTS", "testserver")

# Hypothesis under mutation testing. mutmut runs the stats pass and the
# clean pass as two pytest sessions in one process, so every property
# test is called from two executors; Hypothesis flags that as a health
# check because it can make database replay non-reproducible. Under
# mutmut the database is disposable and the seed is fixed, so the check
# says nothing about the property. Selected with --hypothesis-profile=mutation
# from [tool.mutmut] in pyproject.toml; never the default.
try:
    from hypothesis import HealthCheck as _HealthCheck
    from hypothesis import settings as _hypothesis_settings
except ImportError:  # pragma: no cover - hypothesis is a dev dependency
    pass
else:
    _hypothesis_settings.register_profile(
        "mutation",
        derandomize=True,
        suppress_health_check=[_HealthCheck.differing_executors],
    )


class SLOMonitor:
    """Tracks execution time and enforces SLOs."""

    def __init__(self, threshold_secs: float, name: str) -> None:
        self.threshold = threshold_secs
        self.name = name
        self.start_time: float | None = None
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
    # mutmut runs one pytest session per mutant, in parallel forked
    # children. pytest empties a pinned basetemp when a session starts, so
    # a shared one let each child delete its neighbours' files mid-test,
    # and those unrelated failures were counted as killed mutants (the
    # few points of run-to-run variance in the mutation score). Each
    # child gets its own; mutmut sets MUTANT_UNDER_TEST before the
    # session starts.
    basetemp = tmp_root / "pytest"
    if os.environ.get("MUTANT_UNDER_TEST"):
        basetemp = tmp_root / f"pytest-mutant-{os.getpid()}"
    config.option.basetemp = str(basetemp)

    if config.getoption("--enforce-slos"):
        config.addinivalue_line(
            "markers", "slo: mark test as subject to SLO enforcement"
        )
        config.pluginmanager.register(SLOPlugin())
