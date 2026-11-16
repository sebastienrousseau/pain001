# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""The execution summary report, field by field.

The clock is frozen and ``log_event`` captured, so each test compares
the whole summary a run emits rather than spot-checking a key.
"""

from __future__ import annotations

import logging
import time
from importlib import import_module
from types import SimpleNamespace
from typing import Any

import pytest

from pain001.logging_schema.schema import Events
from pain001.logging_schema.tracker import ExecutionSummaryTracker

tracker_mod = import_module("pain001.logging_schema.tracker")
FROZEN = time.struct_time((2026, 1, 2, 3, 4, 5, 4, 2, 0))
STAMP = "2026-01-02T03:04:05Z"
ZERO_COUNTS = {"debug": 0, "info": 0, "warning": 0, "error": 0, "critical": 0}


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Freeze the clock at 1000.0 then 1002.5 and capture summaries."""
    ticks = iter([1000.0, 1002.5])
    clock = SimpleNamespace(
        time=lambda: next(ticks),
        gmtime=lambda: FROZEN,
        strftime=time.strftime,
    )
    captured: list[dict[str, Any]] = []

    def capture(logger: Any, level: int, event: str, **fields: Any) -> None:
        captured.append({"level": level, "event": event, **fields})

    monkeypatch.setattr(tracker_mod, "time", clock)
    monkeypatch.setattr(tracker_mod, "log_event", capture)
    return captured


def _logger() -> logging.Logger:
    """Return the logger the tracker reports to."""
    return logging.getLogger("tracker-test")


def test_fresh_tracker_state() -> None:
    """A new tracker has no times, no files, zero counts and no flags."""
    tracker = ExecutionSummaryTracker(_logger())
    assert tracker.dry_run is False
    assert tracker.message_type is None
    assert (tracker.start_time, tracker.end_time) == (None, None)
    assert (tracker.start_time_iso, tracker.end_time_iso) == (None, None)
    assert (tracker.output_file, tracker.log_file) == (None, None)
    assert tracker.counts == ZERO_COUNTS
    assert tracker.has_errors is False
    assert tracker.has_warnings is False
    assert tracker.aborted is False


def test_full_production_summary(emitted: list[dict[str, Any]]) -> None:
    """Every tracked metric appears in the one summary event."""
    tracker = ExecutionSummaryTracker(
        _logger(), message_type="pain.001.001.09"
    )
    tracker.start()
    for level in ("DEBUG", "info", "Info", "warning", "critical", "trace"):
        tracker.increment_event_count(level)
    tracker.increment_processed_records()
    tracker.increment_processed_records(4)
    tracker.set_validation_result("schema_validation", "PASSED")
    tracker.set_output_file("out.xml")
    tracker.set_log_file("run.log")
    tracker.log_summary()
    assert emitted == [
        {
            "level": logging.INFO,
            "event": Events.EXECUTION_SUMMARY,
            "message": "Execution Summary Report",
            "summary": {
                "status": "FAILED",
                "execution_mode": "production",
                "total_records_processed": 5,
                "counts": {
                    "debug": 1,
                    "info": 2,
                    "warning": 1,
                    "error": 0,
                    "critical": 1,
                },
                "performance": {
                    "start_time": STAMP,
                    "end_time": STAMP,
                    "total_duration_ms": 2500,
                },
                "validation_metrics": {"schema_validation": "PASSED"},
                "artifacts": {"output_file": "out.xml", "log_file": "run.log"},
                "message_type": "pain.001.001.09",
            },
        }
    ]
    assert tracker.end_time_iso == STAMP


def test_unstarted_summary_has_placeholders(
    emitted: list[dict[str, Any]],
) -> None:
    """Without start, files or type, the summary uses placeholders."""
    ExecutionSummaryTracker(_logger()).log_summary()
    summary = emitted[0]["summary"]
    assert summary == {
        "status": "SUCCESS",
        "execution_mode": "production",
        "total_records_processed": 0,
        "counts": ZERO_COUNTS,
        "performance": {
            "start_time": None,
            "end_time": STAMP,
            "total_duration_ms": 0,
        },
        "artifacts": {"output_file": "None", "log_file": "None"},
    }


def test_dry_run_reports_no_output(emitted: list[dict[str, Any]]) -> None:
    """A dry run labels its missing output file as such."""
    ExecutionSummaryTracker(_logger(), dry_run=True).log_summary()
    summary = emitted[0]["summary"]
    assert summary["execution_mode"] == "dry_run"
    assert summary["artifacts"]["output_file"] == "None (Dry Run)"


@pytest.mark.parametrize(
    ("levels", "status", "errors", "warnings"),
    [
        ((), "SUCCESS", False, False),
        (("info", "debug"), "SUCCESS", False, False),
        (("WARNING",), "COMPLETED_WITH_WARNINGS", False, True),
        (("Critical",), "FAILED", True, False),
        (("error", "warning"), "FAILED", True, True),
    ],
)
def test_status_follows_event_levels(
    levels: tuple[str, ...],
    status: str,
    errors: bool,
    warnings: bool,
    emitted: list[dict[str, Any]],
) -> None:
    """Errors fail a run, warnings qualify it, other levels do not."""
    tracker = ExecutionSummaryTracker(_logger())
    for level in levels:
        tracker.increment_event_count(level)
    tracker.log_summary()
    assert emitted[0]["summary"]["status"] == status
    assert tracker.has_errors is errors
    assert tracker.has_warnings is warnings


def _boom() -> None:
    """Fail the way a processing step would."""
    raise RuntimeError("boom")


def test_exception_in_context_aborts_and_counts_error(
    emitted: list[dict[str, Any]],
) -> None:
    """Leaving the context on an exception records one error, aborted."""
    with (
        pytest.raises(RuntimeError),
        ExecutionSummaryTracker(_logger()) as tracker,
    ):
        _boom()
    summary = emitted[0]["summary"]
    assert summary["status"] == "ABORTED"
    assert summary["counts"]["error"] == 1
    assert summary["performance"]["total_duration_ms"] == 2500
    assert tracker.has_errors is True
