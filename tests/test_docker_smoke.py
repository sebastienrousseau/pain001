# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Smoke tests for the bundled Dockerfile (issue #169).

The tests are skipped when Docker is unavailable - locally on machines
without a daemon, and inside CI runs where `docker.yml` already exercises
the image end-to-end. When Docker is present they build the image, exec
the CLI inside it, and assert the same import / non-root / version
invariants the CI workflow checks.

Static guards on the workflow file + Dockerfile run unconditionally so a
careless edit cannot bypass the smoke gate.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
WORKFLOW = ROOT / ".github" / "workflows" / "docker.yml"


def _docker_available() -> bool:
    """Return ``True`` when a usable docker CLI is on PATH."""
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return False
    return True


# ---------------------------------------------------------------------------
# Static guards (always run)
# ---------------------------------------------------------------------------
def test_dockerfile_uses_supported_python() -> None:
    """Image base must be a currently-supported CPython slim variant.

    Pain001 requires Python 3.10+; the image must agree.
    """
    text = DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(r"FROM python:(\d+)\.(\d+)-slim", text)
    assert match, "Dockerfile must FROM python:X.Y-slim"
    major, minor = int(match.group(1)), int(match.group(2))
    assert (major, minor) >= (
        3,
        10,
    ), f"Image Python {major}.{minor} is below 3.10"


def test_dockerfile_installs_api_extra() -> None:
    """Image must ship the ``api`` extra so ``pain001 serve`` works.

    Acceptance criterion 3 of issue #169.
    """
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert '".[api]"' in text or "'.[api]'" in text or "[api]" in text, (
        "Dockerfile must install the api extra"
    )


def test_dockerfile_runs_as_non_root() -> None:
    """Hardening: image must `USER` to a non-root account.

    Acceptance criterion 5 of issue #169.
    """
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "USER pain001" in text, "Dockerfile must USER pain001"
    assert "groupadd --system pain001" in text


def test_dockerfile_has_healthcheck() -> None:
    """Image must declare a HEALTHCHECK."""
    assert "HEALTHCHECK" in DOCKERFILE.read_text(encoding="utf-8")


def test_workflow_publishes_multi_arch() -> None:
    """Workflow must publish multi-arch (amd64 + arm64) to GHCR.

    Acceptance criterion 4 of issue #169.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "linux/amd64" in text
    assert "linux/arm64" in text
    # Anchored env declaration rather than a bare substring so static
    # analysers (CodeQL py/incomplete-url-substring-sanitization) can
    # see this is a workflow content check, not a URL host check.
    assert "REGISTRY: ghcr.io" in text


def test_workflow_tags_from_semver_and_latest() -> None:
    """Workflow must derive tags from semver + `latest` on default branch.

    Acceptance criterion 4 of issue #169: tagged with both the exact
    version and `latest`.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "type=semver,pattern={{version}}" in text
    assert "type=raw,value=latest" in text


def test_workflow_smoke_test_step_present() -> None:
    """Workflow must smoke-test the pulled image (acceptance criterion 1+5)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Smoke-test the published image" in text
    # Checks the version
    assert "--version" in text
    # Checks the non-root user
    assert "whoami" in text


# ---------------------------------------------------------------------------
# Live smoke (only when docker is available)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def built_image() -> str:
    """Build the image once per test session and return its tag."""
    if not _docker_available() or os.environ.get("PAIN001_SKIP_DOCKER_SMOKE"):
        pytest.skip("docker not available")
    # docker.yml already exercises the multi-arch image end-to-end on
    # every push; running `docker build` here as well doubles CI time
    # and is flaky on the shared runner.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        pytest.skip("docker.yml workflow already exercises the image")
    tag = "pain001-smoke:test"
    subprocess.run(
        ["docker", "build", "-t", tag, str(ROOT)],
        check=True,
        capture_output=True,
    )
    return tag


def test_image_version_matches_package(built_image: str) -> None:
    """``pain001 --version`` inside the container matches the package version.

    Acceptance criterion 1 of issue #169.
    """
    import pain001

    out = subprocess.run(
        ["docker", "run", "--rm", built_image, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    combined = (out.stdout + out.stderr).strip()
    assert pain001.__version__ in combined, (
        f"`pain001 --version` output {combined!r} does not contain "
        f"the package version {pain001.__version__}"
    )


def test_image_runs_as_pain001_user(built_image: str) -> None:
    """Container starts as the non-root ``pain001`` user.

    Acceptance criterion 5 of issue #169.
    """
    out = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "whoami", built_image],
        check=True,
        capture_output=True,
        text=True,
    )
    assert out.stdout.strip() == "pain001"


def test_image_import_check_succeeds(built_image: str) -> None:
    """The HEALTHCHECK's import probe is reproduced by hand."""
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "python",
            built_image,
            "-c",
            "import pain001; import pain001.api.app",
        ],
        check=True,
        capture_output=True,
    )
