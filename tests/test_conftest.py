# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Tests for conftest pytest plugin."""

from conftest import SLOMonitor, SLOPlugin, pytest_addoption


class TestSLOMonitor:
    """Test SLOMonitor class."""

    def test_slo_monitor_init(self):
        """Test SLOMonitor initialization."""
        monitor = SLOMonitor(10.0, "Test")
        assert monitor.threshold == 10.0
        assert monitor.name == "Test"
        assert monitor.elapsed == 0.0
        assert monitor.start_time is None

    def test_slo_monitor_start_stop(self):
        """Test SLOMonitor start and stop."""
        monitor = SLOMonitor(10.0, "Test")
        monitor.start()
        assert monitor.start_time is not None
        elapsed = monitor.stop()
        assert elapsed >= 0.0
        assert monitor.elapsed >= 0.0

    def test_slo_monitor_exceeded_false(self):
        """Test SLOMonitor exceeded when not exceeded."""
        monitor = SLOMonitor(10.0, "Test")
        monitor.elapsed = 5.0
        assert not monitor.exceeded()

    def test_slo_monitor_exceeded_true(self):
        """Test SLOMonitor exceeded when exceeded."""
        monitor = SLOMonitor(5.0, "Test")
        monitor.elapsed = 10.0
        assert monitor.exceeded()

    def test_slo_monitor_report_ok(self):
        """Test SLOMonitor report when OK."""
        monitor = SLOMonitor(10.0, "Linting")
        monitor.elapsed = 5.0
        report = monitor.report()
        assert "Linting" in report
        assert "5.00s" in report
        assert "10.0s" in report
        assert "✓ OK" in report

    def test_slo_monitor_report_exceeded(self):
        """Test SLOMonitor report when exceeded."""
        monitor = SLOMonitor(5.0, "Linting")
        monitor.elapsed = 10.0
        report = monitor.report()
        assert "Linting" in report
        assert "10.00s" in report
        assert "5.0s" in report
        assert "✗ EXCEEDED" in report


class TestSLOPlugin:
    """Test SLOPlugin class."""

    def test_slo_plugin_init(self):
        """Test SLOPlugin initialization."""
        plugin = SLOPlugin()
        assert plugin.session_monitor is not None
        assert plugin.lint_monitor is not None
        assert plugin.type_monitor is not None
        assert len(plugin.monitors) == 3

    def test_slo_plugin_monitors_have_correct_thresholds(self):
        """Test SLOPlugin monitors have correct thresholds."""
        plugin = SLOPlugin()
        assert plugin.session_monitor.threshold == 60.0
        assert plugin.lint_monitor.threshold == 15.0
        assert plugin.type_monitor.threshold == 10.0

    def test_pytest_configure(self):
        """Test pytest_configure hook."""
        plugin = SLOPlugin()
        # Create a mock config object
        config = type("Config", (), {})()
        # Just ensure it doesn't raise
        plugin.pytest_configure(config)

    def test_pytest_sessionfinish(self, capsys):
        """Test pytest_sessionfinish hook."""
        plugin = SLOPlugin()
        plugin.session_monitor.elapsed = 30.0
        plugin.lint_monitor.elapsed = 10.0
        plugin.type_monitor.elapsed = 5.0

        # Create a mock session
        session = type("Session", (), {})()
        plugin.pytest_sessionfinish(session, 0)

        # Check output was printed
        captured = capsys.readouterr()
        assert "PySentinel SLO Report" in captured.out
        assert "Test Suite" in captured.out


def test_pytest_addoption():
    """Test pytest_addoption hook is callable."""
    # Create a mock parser
    parser = type(
        "Parser", (), {"addoption": lambda self, *args, **kwargs: None}
    )()

    # Just ensure it doesn't raise
    pytest_addoption(parser)
