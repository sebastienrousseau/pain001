# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""A cancelled async job stops, writes nothing and stays cancelled."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pain001.api.app import _process_generation_job
from pain001.api.job_manager import JobCancelledError, JobStatus, job_manager
from pain001.api.metrics import registry
from pain001.api.models import GenerateXMLRequest

_CSV = "pain001/templates/pain.001.001.03/template.csv"
# The package re-exports a FastAPI instance named ``app``, which shadows
# the submodule; reach the modules through ``sys.modules``.
_PIPELINE = sys.modules["pain001.api._pipeline"]
_APP = sys.modules["pain001.api.app"]


def _request(output_dir: Path) -> GenerateXMLRequest:
    return GenerateXMLRequest(
        data_source="csv",
        file_path=_CSV,
        message_type="pain.001.001.03",
        output_dir=str(output_dir),
    )


def _outputs(output_dir: Path) -> list[Path]:
    return list(output_dir.glob("pain.001.001.03-*.xml"))


def test_cancel_while_loading_stops_before_rendering(tmp_path):
    """A cancel during the load is seen at the next stage boundary."""
    job_id = job_manager.create_job()
    real_load = _PIPELINE.load_batch

    def load_then_cancel(*args, **kwargs):
        rows = real_load(*args, **kwargs)
        assert job_manager.cancel_job(job_id)
        return rows

    with (
        patch.object(_PIPELINE, "load_batch", side_effect=load_then_cancel),
        patch.object(_PIPELINE, "generate_xml") as render,
    ):
        asyncio.run(_process_generation_job(job_id, _request(tmp_path)))

    render.assert_not_called()
    assert _outputs(tmp_path) == []
    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELLED


def test_cancel_while_rendering_removes_the_file(tmp_path):
    """A cancel that lands during the render leaves no file behind."""
    job_id = job_manager.create_job()
    real_render = _PIPELINE.generate_xml

    def render_then_cancel(*args, **kwargs):
        written = real_render(*args, **kwargs)
        assert Path(written).is_file()
        assert job_manager.cancel_job(job_id)
        return written

    with patch.object(
        _PIPELINE, "generate_xml", side_effect=render_then_cancel
    ):
        asyncio.run(_process_generation_job(job_id, _request(tmp_path)))

    assert _outputs(tmp_path) == []
    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELLED
    assert job.result is None


def test_cancel_after_the_last_stage_keeps_the_job_cancelled(tmp_path):
    """A validate-only job cancelled while validating reports nothing."""
    job_id = job_manager.create_job()
    real_validate = _PIPELINE.SchemaValidator.validate_batch

    def validate_then_cancel(self, data):
        assert job_manager.cancel_job(job_id)
        return real_validate(self, data)

    request = _request(tmp_path).model_copy(update={"validate_only": True})
    with patch.object(
        _PIPELINE.SchemaValidator, "validate_batch", validate_then_cancel
    ):
        asyncio.run(_process_generation_job(job_id, request))

    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELLED
    assert job.result is None


def test_cancelled_job_is_not_counted_as_a_failure(tmp_path):
    """Stopping a cancelled job is neither a failure nor logged as one."""
    job_id = job_manager.create_job()
    assert job_manager.cancel_job(job_id)
    with (
        patch.object(registry, "record_file_processed") as counted,
        patch.object(_APP.logger, "exception") as logged,
    ):
        asyncio.run(_process_generation_job(job_id, _request(tmp_path)))
    counted.assert_not_called()
    logged.assert_not_called()
    assert _outputs(tmp_path) == []


def test_raise_if_cancelled():
    """The check raises for a cancelled job only."""
    job_id = job_manager.create_job()
    job_manager.raise_if_cancelled(job_id)
    job_manager.raise_if_cancelled("no-such-job")
    job_manager.cancel_job(job_id)
    with pytest.raises(JobCancelledError):
        job_manager.raise_if_cancelled(job_id)
