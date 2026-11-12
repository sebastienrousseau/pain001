# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The tag workflow builds without credentials and publishes without building.

Up to 0.0.86 one job built the distributions and held the PyPI OIDC
token, so every tool the build ran (Poetry, the build backend, the SBOM
tools) ran beside a token that could publish. The build now runs in a
read-only job and the publish job only checks and uploads its output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
JOBS: dict[str, Any] = yaml.load(
    (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
    Loader=yaml.BaseLoader,
)["jobs"]
TAG_ONLY = "startsWith(github.ref, 'refs/tags/v')"


def _uses(job: str) -> list[str]:
    return [step.get("uses", "") for step in JOBS[job]["steps"]]


def test_the_build_job_holds_no_write_permission_or_token() -> None:
    build = JOBS["build"]
    assert build["permissions"] == {"contents": "read"}
    assert "environment" not in build
    assert build["if"] == TAG_ONLY
    assert "cache" not in str(build["steps"])
    assert "steps.dist_hashes.outputs.hashes" in build["outputs"]["hashes"]


def test_the_publish_job_only_downloads_checks_and_uploads() -> None:
    publish = JOBS["publish"]
    assert publish["needs"] == "build"
    assert publish["if"] == TAG_ONLY
    assert publish["environment"] == "pypi"
    assert publish["permissions"]["id-token"] == "write"
    uses = _uses("publish")
    assert not any(u.startswith("actions/checkout@") for u in uses)
    assert not any(u.startswith("actions/setup-python@") for u in uses)
    assert uses[0].startswith("actions/download-artifact@")
    runs = "\n".join(s.get("run", "") for s in publish["steps"])
    assert "sha256sum --check --strict" in runs
    for tool in ("poetry", "pip install", "python -m build"):
        assert tool not in runs


def test_provenance_subjects_come_from_the_build_job() -> None:
    provenance = JOBS["provenance"]
    assert provenance["needs"] == ["build", "publish"]
    assert (
        provenance["with"]["base64-subjects"]
        == "${{ needs.build.outputs.hashes }}"
    )
    assert "needs.publish.outputs" not in str(JOBS)


def test_the_published_image_is_built_without_the_shared_cache() -> None:
    """Only pull-request builds, which push nothing, use the GHA cache."""
    docker = yaml.load(
        (ROOT / ".github/workflows/docker.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    (build,) = [
        step["with"]
        for job in docker["jobs"].values()
        for step in job["steps"]
        if "docker/build-push-action" in step.get("uses", "")
    ]
    pr_only = "github.event_name == 'pull_request' && 'type=gha"
    assert pr_only in build["cache-from"]
    assert pr_only in build["cache-to"]
