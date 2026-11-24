"""
PySentinel pytest plugin for real-time SLO enforcement.
Monitors test execution time and warns if approaching thresholds.
"""

import logging
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

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


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Leave only files and directories in the pinned basetemp.

    The basetemp sits under pain001/tmp, inside the package tree that
    ``poetry build`` walks. A symlink out of the tree, a dangling one or
    a named pipe left there by a test makes the build fail, so the
    release preflight, which builds right after the suite, would too.
    """
    basetemp = Path(session.config.option.basetemp)
    special = [
        path
        for path in basetemp.rglob("*")
        if path.is_symlink() or not (path.is_file() or path.is_dir())
    ]
    for path in special:
        path.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _no_trace_context_leak(request: pytest.FixtureRequest) -> Iterator[None]:
    """Run each test in an empty OpenTelemetry context; fail one that leaks.

    Starlette's TestClient runs the app in the calling thread's context,
    so a span one test leaves active would show up in a later test's
    logs (``span_id``), depending on the order tests run in. The module
    is only touched once something has imported it, as in the product.
    """
    context = sys.modules.get("opentelemetry.context")
    token = context.attach(context.Context()) if context else None
    yield
    trace = sys.modules.get("opentelemetry.trace")
    active = (
        trace is not None
        and trace.get_current_span().get_span_context().is_valid
    )
    if context is not None and token is not None:
        context.detach(token)
    assert not active, (
        f"{request.node.nodeid} left an OpenTelemetry span active"
    )


@pytest.fixture(autouse=True)
def _no_global_tracer_provider(
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    """Fail a test that installs a process-wide tracer provider.

    OpenTelemetry lets a process set its provider once. A test that
    reaches the real ``init_otel`` with ``OTEL_ENABLED`` set installs one
    for good, and every later tracing test then sees its spans and its
    service name, depending on the order tests run in. pain001's cached
    tracer is cleared after each test for the same reason.
    """
    yield
    otel = cast(Any, sys.modules.get("pain001.observability.otel"))
    if otel is not None:
        otel.reset_for_tests()
    trace = sys.modules.get("opentelemetry.trace")
    assert trace is None or isinstance(
        trace.get_tracer_provider(), trace.ProxyTracerProvider
    ), f"{request.node.nodeid} installed a global tracer provider"


@pytest.fixture(autouse=True)
def _restore_package_logger() -> Iterator[None]:
    """Put the ``pain001`` logger back as the test found it.

    The logger is process-wide: a test that sets it to WARNING (through
    ``Context.set_log_level``) silences the INFO events a later test
    captures with ``caplog``, depending on the order tests run in, as
    mutmut's clean-test pass does.
    """
    package = logging.getLogger("pain001")
    saved = (package.level, package.propagate, package.disabled)
    handlers = list(package.handlers)
    context = cast(Any, sys.modules.get("pain001.context.context"))
    instance = context.Context.instance if context is not None else None
    level = getattr(instance, "log_level", None)
    yield
    package.setLevel(saved[0])
    package.propagate, package.disabled = saved[1], saved[2]
    package.handlers = handlers
    if instance is not None and level is not None:
        instance.log_level = level


@pytest.fixture(autouse=True)
def _wait_for_pipeline_jobs() -> Iterator[None]:
    """Let a test's background REST jobs finish before the next test starts.

    The API runs generation on a thread pool and a job can outlive the
    request that started it. Work still running after its test would be
    attributed to whichever test runs next (mutmut picks the tests to run
    against a mutant from that record), so the pool is drained here.
    """
    yield
    pipeline = cast(Any, sys.modules.get("pain001.api._pipeline"))
    if pipeline is not None and pipeline._executor is not None:
        pipeline._executor.shutdown(wait=True)
        pipeline._executor = None
