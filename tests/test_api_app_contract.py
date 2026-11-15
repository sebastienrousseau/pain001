# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Contract of the REST app's path guards and its background job.

The guards decide which status and detail a caller sees for a path it
may not use; the background job decides what ``/status`` reports and
what ``/metrics`` counts. Both are pinned here exactly.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from pain001.api._pipeline import GenerationOutcome
from pain001.api.job_manager import JobStatus, job_manager
from pain001.api.metrics import registry
from pain001.api.models import GenerateXMLRequest

# ``pain001.api`` re-exports the FastAPI instance as ``app``, which
# shadows the submodule on attribute access.
app_module = importlib.import_module("pain001.api.app")

DENIED = "Access denied: path outside allowed directory"
MESSAGE_TYPE = "pain.001.001.03"


@pytest.fixture
def clean_registry() -> Iterator[None]:
    """Run with an empty metrics registry and leave it empty."""
    registry.reset()
    yield
    registry.reset()


def _refusal(path: str, base_dir: Path | None = None) -> HTTPException:
    """Return the HTTPException ``_validate_safe_path`` raises for ``path``."""
    with pytest.raises(HTTPException) as info:
        app_module._validate_safe_path(path, base_dir)
    return info.value


def test_base_dir_confines_the_path(tmp_path: Path) -> None:
    """With a base directory, only paths under it are accepted."""
    inside = tmp_path / "base" / "f.csv"
    resolved = app_module._validate_safe_path(str(inside), tmp_path / "base")
    assert resolved == inside.resolve()
    refused = _refusal(str(tmp_path / "other.csv"), tmp_path / "base")
    assert (refused.status_code, refused.detail) == (403, DENIED)


def test_refusals_carry_exact_details() -> None:
    """Traversal is 400 ``Invalid path``; escaping is 403 access denied."""
    invalid = _refusal("a/../b.csv")
    assert (invalid.status_code, invalid.detail) == (400, "Invalid path")
    outside = _refusal("/etc/passwd")
    assert (outside.status_code, outside.detail) == (403, DENIED)


def test_allowed_roots_themselves_are_accepted() -> None:
    """The working and temporary directories are valid paths."""
    cwd = Path.cwd().resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    assert app_module._validate_safe_path(str(cwd)) == cwd
    assert app_module._validate_safe_path(str(tmp)) == tmp


def test_barrier_refuses_what_the_validator_lets_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resolved path outside both roots is refused even if validated."""
    monkeypatch.setattr(
        app_module, "validate_path", lambda *a, **k: "/nonexistent-root/x"
    )
    refused = _refusal("x.csv")
    assert (refused.status_code, refused.detail) == (403, DENIED)


def test_output_dir_barrier_refuses_other_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``output_dir`` outside both roots is 403 even past the first guard."""
    monkeypatch.setattr(app_module, "_validate_safe_path", Path)
    with pytest.raises(HTTPException) as info:
        app_module._gate_output_dir("/")
    assert info.value.status_code == 403
    assert info.value.detail == (
        "Access denied: output_dir outside allowed directory"
    )


def test_output_dir_parents_are_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A nested ``output_dir`` that does not exist yet is created."""
    monkeypatch.chdir(tmp_path)
    nested = tmp_path / "a" / "b"
    request = GenerateXMLRequest(
        data_source="csv",
        file_path="in.csv",
        message_type=MESSAGE_TYPE,
        output_dir=str(nested),
    )
    output, _, _ = app_module._resolve_generation_paths(request)
    assert nested.is_dir()
    assert Path(output).parent == nested.resolve()


def test_missing_input_and_unknown_job_details() -> None:
    """A missing file and an unknown job are 404s that say which."""
    client = TestClient(app_module.app)
    missing = client.post(
        "/api/v1/generate",
        json={
            "data_source": "csv",
            "file_path": "no-such-file.csv",
            "message_type": MESSAGE_TYPE,
        },
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "File not found"}
    unknown = client.get("/api/v1/status/no-such-job")
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Job not found: no-such-job"}


@pytest.fixture
def job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Create a pending job; work in ``tmp_path`` holding ``in.csv``."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "in.csv").write_text("x\n", encoding="utf-8")
    job_id = job_manager.create_job()
    yield job_id
    job_manager.jobs.pop(job_id, None)


def _process(
    job_id: str,
    monkeypatch: pytest.MonkeyPatch,
    result: Any,
    path: str = "in.csv",
) -> None:
    """Run the background job with a pipeline that returns or raises."""

    async def fake_pipeline(*_args: Any) -> Any:
        if isinstance(result, BaseException):
            raise result
        if callable(result):
            return result()
        return result

    monkeypatch.setattr(app_module, "run_pipeline", fake_pipeline)
    request = GenerateXMLRequest(
        data_source="csv", file_path=path, message_type=MESSAGE_TYPE
    )
    asyncio.run(app_module._process_generation_job(job_id, request))


def _processed() -> list[str]:
    """Return the rendered files-processed counter samples."""
    return registry.render("pain001_files_processed_total")


def _label(status: str) -> str:
    """Return the files-processed sample for one outcome status."""
    return (
        'pain001_files_processed_total{message_type="pain.001.001.03",'
        f'status="{status}"}} 1.0'
    )


@pytest.mark.usefixtures("clean_registry")
def test_job_success_is_complete_and_counted(
    job: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generated file ends the job at 100 % and counts a success."""
    outcome = GenerationOutcome("generated", 1, 1, file_path="out.xml")
    _process(job, monkeypatch, outcome)
    record = job_manager.jobs[job]
    assert record.status is JobStatus.SUCCESS
    assert record.progress_percent == 100
    assert _processed() == [_label("success")]


@pytest.mark.usefixtures("clean_registry")
def test_job_refused_input_is_failed_and_counted(
    job: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing input file fails the job with the refusal's detail."""
    _process(job, monkeypatch, AssertionError("unreached"), path="gone.csv")
    record = job_manager.jobs[job]
    assert (record.status, record.error) == (
        JobStatus.FAILED,
        "File not found",
    )
    assert _processed() == [_label("failure")]


@pytest.mark.usefixtures("clean_registry")
def test_job_crash_is_failed_logged_and_counted(
    job: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A crash is logged with the job id and reported generically."""
    with caplog.at_level(logging.ERROR, logger="pain001.api.app"):
        _process(job, monkeypatch, RuntimeError("internal detail"))
    record = job_manager.jobs[job]
    assert record.status is JobStatus.FAILED
    assert record.progress_percent == 100
    assert record.error == "Processing failed"
    assert [r.getMessage() for r in caplog.records] == [f"Job {job} failed"]
    assert caplog.records[0].exc_info is not None
    assert _processed() == [_label("failure")]


@pytest.mark.usefixtures("clean_registry")
@pytest.mark.parametrize("file_exists", [True, False])
def test_job_cancelled_mid_render_discards_its_file(
    job: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    file_exists: bool,
) -> None:
    """A job cancelled while rendering loses its file and counts nothing."""
    output = tmp_path / "late.xml"

    def cancel_then_finish() -> GenerationOutcome:
        job_manager.cancel_job(job)
        if file_exists:
            output.write_text("<x/>", encoding="utf-8")
        return GenerationOutcome("generated", 1, 1, file_path=str(output))

    _process(job, monkeypatch, cancel_then_finish)
    assert job_manager.jobs[job].status is JobStatus.CANCELLED
    assert not output.exists()
    assert _processed() == []
