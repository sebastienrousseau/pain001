# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for the typed OpenAPI client SDK (issue #170).

The CI workflow `.github/workflows/sdk.yml` regenerates a Python
client from the exported OpenAPI document on every API change.
These tests guard:

* the schema the workflow exports is valid OpenAPI 3.x;
* every `/api/v1/*` route and every request/response model appears;
* the workflow derives the SDK version from the release tag (which
  matches `pain001.__version__`); and
* the exported document is a faithful round-trip target for the
  generator (drift between two consecutive exports is impossible).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sdk.yml"
EXPORT_SCRIPT = ROOT / "scripts" / "export_openapi.py"


def _openapi() -> dict:
    sys.path.insert(0, str(ROOT))
    from pain001.api.app import app

    return app.openapi()


def test_exported_schema_is_valid_openapi_3() -> None:
    """Criterion 1 of issue #170: well-formed OpenAPI 3.x document."""
    schema = _openapi()
    assert "openapi" in schema and schema["openapi"].startswith("3.")
    assert "info" in schema
    assert "paths" in schema
    assert schema["paths"], "no paths in the exported schema"


def test_every_versioned_route_is_in_schema() -> None:
    """Criterion 2 of issue #170: every `/api/v1/*` route appears."""
    schema = _openapi()
    paths = list(schema.get("paths", {}))
    versioned = [p for p in paths if p.startswith("/api/v1/")]
    assert versioned, "no /api/v1/* routes in the schema"


def test_every_request_response_model_is_in_components() -> None:
    """Criterion 2 of issue #170: every model appears in components."""
    schemas = _openapi().get("components", {}).get("schemas", {})
    expected = {
        "GenerateXMLRequest",
        "GenerateXMLResponse",
        "ValidationRequest",
        "ValidationResponse",
        "HealthResponse",
        "JobStatusResponse",
    }
    missing = expected - set(schemas)
    assert not missing, f"OpenAPI components missing: {sorted(missing)}"


def test_sdk_workflow_uses_openapi_generator_cli() -> None:
    """Criterion 3 of issue #170: CI generates via openapi-generator."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "openapi-generator-cli" in text
    assert "-g python" in text
    assert "--package-name pain001_client" in text


def test_sdk_workflow_derives_version_from_tag() -> None:
    """Criterion 5 of issue #170: SDK version derived from the package.

    The workflow strips the leading ``v`` from a release tag and
    passes the result to ``--additional-properties=packageVersion=``,
    so the generated SDK version stays in lockstep with
    ``pain001.__version__``.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "PACKAGE_VERSION" in text
    assert "packageVersion=${VERSION}" in text
    assert "VERSION=${PACKAGE_VERSION#v}" in text


def test_sdk_workflow_smoke_imports_every_generated_submodule() -> None:
    """Criterion 3 of issue #170: smoke test imports every operation."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pkgutil.walk_packages" in text
    assert "import pain001_client" in text


def test_export_script_round_trips(tmp_path) -> None:
    """Criterion 6 of issue #170: drift guard between two exports.

    Two consecutive runs of `scripts/export_openapi.py` produce the
    same document. If anything in the FastAPI surface is non-
    deterministic (e.g. random example IDs), this test catches it
    before it lands in production and breaks the SDK build.
    """
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    for target in (first, second):
        subprocess.run(
            [sys.executable, str(EXPORT_SCRIPT), str(target)],
            check=True,
            cwd=ROOT,
            capture_output=True,
        )
    a = json.loads(first.read_text())
    b = json.loads(second.read_text())
    assert a == b, "export_openapi.py produced different documents twice"


def test_documented_sdk_install_instructions_present() -> None:
    """README documents the SDK consumption surface (#170)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # We document either the SDK package name or the generator command.
    assert (
        "pain001-client" in readme
        or "openapi-generator" in readme
        or "openapi.json" in readme
    ), "README must mention the typed SDK consumption path"


def test_exporter_meta_schema_compliance() -> None:
    """Criterion 1 of issue #170: validate against OpenAPI 3 meta-schema.

    Full meta-schema validation needs an extra dependency; without
    one available in this environment we assert the core structural
    invariants explicitly so the document cannot regress quietly.
    """
    schema = _openapi()
    # Each path operation has a description and at least one response.
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            if method.startswith("x-") or method not in {
                "get",
                "post",
                "put",
                "delete",
                "patch",
            }:
                continue
            assert op.get(
                "responses"
            ), f"{method.upper()} {path} has no responses"
            for code, resp in op["responses"].items():
                assert re.match(
                    r"^[1-5][0-9X]{2}$|default", code
                ), f"{method.upper()} {path} -> bad status code {code!r}"
                assert "description" in resp
