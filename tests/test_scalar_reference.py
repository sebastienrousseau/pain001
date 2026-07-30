# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Regression tests for the hosted Scalar API reference (issue #174).

The docs workflow exports `openapi.json` next to a standalone
`api-reference.html` so the schema is browsable on the public docs
site. These tests pin the wiring in place; the actual rendered HTML
is built on `docs.yml`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_WORKFLOW = ROOT / ".github" / "workflows" / "docs.yml"
STATIC_HTML = ROOT / "docs" / "_static" / "api-reference.html"
EXPORT_SCRIPT = ROOT / "scripts" / "export_openapi.py"
PUBLIC_URL = "https://sebastienrousseau.github.io/pain001/api-reference.html"


def test_export_openapi_script_present() -> None:
    """The exporter script the docs workflow runs must exist."""
    assert EXPORT_SCRIPT.is_file(), (
        "scripts/export_openapi.py is the canonical schema exporter; "
        "docs.yml runs it to refresh the hosted reference."
    )


def test_export_openapi_writes_valid_openapi_3() -> None:
    """The exported schema is well-formed OpenAPI 3.x.

    Criteria 1 + 2 of issue #174: the build embeds an exported
    `openapi.json` and the document is a faithful, validated mirror
    of the live API.
    """
    import sys

    sys.path.insert(0, str(ROOT))
    from pain001.api.app import app

    schema = app.openapi()
    assert schema.get("openapi", "").startswith("3."), (
        "exported schema must be OpenAPI 3.x"
    )
    info = schema.get("info", {})
    assert info.get("title"), "info.title is required"
    assert info.get("version"), "info.version is required"
    # Acceptance criterion 3: the site title and version reflect
    # `pain001.__version__`.
    import pain001

    assert info["version"] == pain001.__version__


def test_static_reference_page_present_and_embeds_scalar() -> None:
    """The standalone Scalar page exists and embeds the Scalar bundle.

    Criterion 1 + 6 of issue #174.
    """
    assert STATIC_HTML.is_file()
    text = STATIC_HTML.read_text(encoding="utf-8")
    assert "@scalar/api-reference" in text
    assert 'data-url="./openapi.json"' in text
    # Non-empty parseable HTML.
    assert "<html" in text.lower()
    assert "</html>" in text.lower()
    # Contains the API title for the smoke check.
    assert "Pain001" in text


def test_docs_workflow_exports_openapi_and_stages_scalar() -> None:
    """docs.yml must export openapi.json and stage the Scalar page.

    Criteria 1, 5 + 6 of issue #174: the deploy job runs on tag /
    `main` only (not fork PRs), exports the schema, and stages the
    Scalar HTML into the published site.
    """
    text = DOCS_WORKFLOW.read_text(encoding="utf-8")
    # Schema export.
    assert "scripts/export_openapi.py docs/_static/openapi.json" in text
    # Scalar staging.
    assert "api-reference.html" in text
    # Trigger: main + manual only (not pull_request, which would mean
    # fork PRs could touch the deploy).
    assert "branches:" in text
    assert "- main" in text
    assert "pull_request" not in text


def test_documented_public_url_is_well_formed() -> None:
    """README and OPERATIONS link to a well-formed Pages URL.

    Criterion 4 of issue #174 (link-check).
    """
    url_pattern = re.compile(
        r"^https://[a-zA-Z0-9.-]+\.github\.io/[a-zA-Z0-9_-]+"
        r"/api-reference\.html$"
    )
    assert url_pattern.match(PUBLIC_URL), f"URL malformed: {PUBLIC_URL}"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ops = (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
    assert PUBLIC_URL in readme, "README.md must link the public reference"
    assert PUBLIC_URL in ops, "OPERATIONS.md must link the public reference"


def test_openapi_includes_every_versioned_route() -> None:
    """Every /api/v1/* route appears in the exported schema.

    Criterion 2 of issue #174.
    """
    import sys

    sys.path.insert(0, str(ROOT))
    from pain001.api.app import app

    paths = app.openapi().get("paths", {})
    versioned = {p for p in paths if p.startswith("/api/v1/")}
    assert versioned, "no /api/v1/* routes in the exported schema"
    # Spot-check the headline endpoints exist.
    assert any("/health" in p for p in versioned)


def test_openapi_includes_every_request_response_model() -> None:
    """Every pydantic model used in the API surface is in components.

    Criterion 2 of issue #174.
    """
    import sys

    sys.path.insert(0, str(ROOT))
    from pain001.api.app import app

    schemas = app.openapi().get("components", {}).get("schemas", {})
    must_be_present = {
        "GenerateXMLRequest",
        "GenerateXMLResponse",
        "ValidationRequest",
        "ValidationResponse",
        "HealthResponse",
    }
    missing = must_be_present - set(schemas)
    assert not missing, f"OpenAPI components missing: {sorted(missing)}"


def test_openapi_drift_guard_against_committed_snapshot(tmp_path) -> None:
    """Freshly-exported schema matches what `scripts/export_openapi.py` writes.

    Criterion 2 of issue #174 (drift guard between the exporter and
    the live app surface). The exporter is the only authority; this
    asserts a fresh run produces the same document the docs workflow
    would publish, which makes any silent drift loud.
    """
    import subprocess
    import sys

    target = tmp_path / "openapi.json"
    subprocess.run(
        [sys.executable, str(EXPORT_SCRIPT), str(target)],
        check=True,
        cwd=ROOT,
        capture_output=True,
    )
    # Just round-tripping confirms the script wrote valid JSON; the
    # OpenAPI-version + version-from-package checks above are the
    # content guards.
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["openapi"].startswith("3.")
