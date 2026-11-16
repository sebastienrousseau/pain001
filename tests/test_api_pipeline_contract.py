# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract of the shared generation pipeline and its response mapping.

``generate_pipeline`` reports progress at fixed stages and returns an
outcome whose counts end up in the ``/generate`` body, the job record
and the metrics. These tests pin those numbers and texts.
"""

from __future__ import annotations

import asyncio
import csv
import shutil
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from pain001.api import _pipeline
from pain001.api._pipeline import (
    GenerationOutcome,
    generate_pipeline,
    job_update,
    record_failure,
    record_outcome,
    reset_executor,
    run_pipeline,
    sync_response,
)
from pain001.api.job_manager import JobStatus
from pain001.api.metrics import registry
from pain001.api.models import GenerateXMLRequest, GenerateXMLResponse
from pain001.constants import TEMPLATES_DIR

MESSAGE_TYPE = "pain.001.001.03"


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Work in a fresh directory holding a good and a bad CSV."""
    monkeypatch.chdir(tmp_path)
    source = TEMPLATES_DIR / MESSAGE_TYPE / "template.csv"
    shutil.copy(source, tmp_path / "good.csv")
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["currency"] = "EURO"  # loads, but fails schema validation
    with (tmp_path / "bad.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return tmp_path


@pytest.fixture
def clean_registry() -> Iterator[None]:
    """Run with an empty metrics registry and leave it empty."""
    registry.reset()
    yield
    registry.reset()


def _request(path: str, **extra: object) -> GenerateXMLRequest:
    """Build a CSV generation request for ``path``."""
    return GenerateXMLRequest(
        data_source="csv", file_path=path, message_type=MESSAGE_TYPE, **extra
    )


def _run(
    request: GenerateXMLRequest, tmp: Path
) -> tuple[GenerationOutcome, list[int]]:
    """Run the pipeline, writing into ``tmp``; return outcome and progress."""
    seen: list[int] = []

    def paths(_req: GenerateXMLRequest) -> tuple[str, str, str]:
        base = TEMPLATES_DIR / MESSAGE_TYPE
        return (
            str(tmp / "out.xml"),
            str(base / f"{MESSAGE_TYPE}.xsd"),
            str(base / "template.xml"),
        )

    outcome = generate_pipeline(request, request.file_path, paths, seen.append)
    return outcome, seen


def test_pipeline_limit_accepts_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """``1`` is the smallest valid concurrency."""
    monkeypatch.setenv("PAIN001_API_CONCURRENCY", "1")
    assert _pipeline.pipeline_limit() == 1


def test_pipelines_run_on_named_threads() -> None:
    """Pipeline threads are named so they show up in a thread dump."""
    reset_executor()
    try:
        name = asyncio.run(
            run_pipeline(lambda: threading.current_thread().name)
        )
    finally:
        reset_executor()
    assert name.startswith("pain001-pipeline_")


def test_reset_executor_does_not_wait_for_running_pipelines() -> None:
    """Dropping the pool returns while a pipeline is still running."""
    reset_executor()
    started, release = threading.Event(), threading.Event()

    def busy() -> None:
        started.set()
        release.wait(10)

    _pipeline._get_executor().submit(busy)
    assert started.wait(5)
    resetter = threading.Thread(target=reset_executor)
    resetter.start()
    resetter.join(2)
    still_waiting = resetter.is_alive()
    release.set()
    resetter.join()
    assert not still_waiting


def test_generated_outcome_and_progress(workdir: Path) -> None:
    """A full run reports 10, 40, 70 and counts every row."""
    outcome, seen = _run(_request("good.csv"), workdir)
    assert seen == [10, 40, 70]
    assert (outcome.kind, outcome.total, outcome.valid) == ("generated", 4, 4)
    assert outcome.file_path == str(workdir / "out.xml")
    assert len(outcome.data) == 4


def test_validate_only_outcome(workdir: Path) -> None:
    """Validate-only stops before rendering, with its counts."""
    outcome, seen = _run(_request("good.csv", validate_only=True), workdir)
    assert seen == [10, 40]
    assert (outcome.kind, outcome.total, outcome.valid) == ("validated", 4, 4)


def test_invalid_rows_outcome(workdir: Path) -> None:
    """Schema failures return the counts and the errors, no file."""
    outcome, _ = _run(_request("bad.csv"), workdir)
    assert (outcome.kind, outcome.total, outcome.valid) == (
        "invalid_rows",
        4,
        3,
    )
    assert len(outcome.errors) == 1
    assert not (workdir / "out.xml").exists()


def test_scheme_failed_outcome(workdir: Path) -> None:
    """A failing scheme names its profile and keeps the counts."""
    outcome, _ = _run(_request("good.csv", scheme="uk-fps"), workdir)
    assert (outcome.kind, outcome.total, outcome.valid) == (
        "scheme_failed",
        4,
        4,
    )
    assert outcome.profile == "uk-fps"
    assert outcome.violations


def _processed() -> list[str]:
    """Return the rendered files-processed counter samples."""
    return registry.render("pain001_files_processed_total")


def _seconds_sum() -> float:
    """Return the recorded processing-seconds sum."""
    lines = registry.render_summaries("pain001_processing_seconds")
    sum_line = next(ln for ln in lines if "_sum" in ln)
    return float(sum_line.rsplit(" ", 1)[1])


@pytest.mark.usefixtures("clean_registry")
def test_record_failure_times_from_the_start() -> None:
    """A failure counts once and records the time since the start."""
    record_failure(MESSAGE_TYPE, time.perf_counter() - 0.5)
    assert _processed() == [
        'pain001_files_processed_total{message_type="pain.001.001.03",'
        'status="failure"} 1.0'
    ]
    assert 0.5 <= _seconds_sum() < 30


@pytest.mark.usefixtures("clean_registry")
def test_record_outcome_per_kind() -> None:
    """Generated is a success, refused data a failure, validate-only nothing."""
    start = time.perf_counter() - 0.5
    record_outcome(GenerationOutcome("validated", 1, 1), MESSAGE_TYPE, start)
    assert _processed() == []
    record_outcome(GenerationOutcome("generated", 1, 1), MESSAGE_TYPE, start)
    assert 0.5 <= _seconds_sum() < 30
    record_outcome(
        GenerationOutcome("invalid_rows", 2, 1), MESSAGE_TYPE, start
    )
    assert _processed() == [
        'pain001_files_processed_total{message_type="pain.001.001.03",'
        + 'status="failure"} 1.0',
        'pain001_files_processed_total{message_type="pain.001.001.03",'
        + 'status="success"} 1.0',
    ]


def test_sync_response_for_a_generated_file() -> None:
    """A generated file is reported with its path and fixed message."""
    body = sync_response(
        GenerationOutcome("generated", 1, 1, file_path="o.xml")
    )
    assert isinstance(body, GenerateXMLResponse)
    assert body.model_dump() == {
        "success": True,
        "message": "XML generated successfully",
        "file_path": "o.xml",
        "validation_errors": [],
        "scheme_violations": [],
    }


def test_job_update_for_generated_and_validated() -> None:
    """Successful outcomes become exact success updates."""
    assert job_update(
        GenerationOutcome("generated", 1, 1, file_path="o.xml")
    ) == {
        "status": JobStatus.SUCCESS,
        "result": {
            "success": True,
            "message": "✓ XML generated successfully",
            "file_path": "o.xml",
            "validation_errors": [],
        },
    }
    assert job_update(GenerationOutcome("validated", 3, 3)) == {
        "status": JobStatus.SUCCESS,
        "result": {
            "success": True,
            "message": "All 3 rows are valid",
            "file_path": None,
        },
    }


def test_job_update_for_a_failed_scheme() -> None:
    """A scheme failure lists the broken rules, in order."""
    from pain001.validation._scheme_types import SchemeViolation

    violations = [
        SchemeViolation("UK-FPS-CCY", "not GBP", 0, "currency"),
        SchemeViolation("UK-FPS-SVCLVL", "no level", 1),
    ]
    update = job_update(
        GenerationOutcome("scheme_failed", 2, 2, violations=violations)
    )
    assert update == {
        "status": JobStatus.FAILED,
        "error": "Scheme validation failed: UK-FPS-CCY, UK-FPS-SVCLVL",
        "result": {
            "success": False,
            "message": "Scheme validation failed",
            "scheme_violations": [v.as_dict() for v in violations],
        },
    }
