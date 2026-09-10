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

"""The single-file dashboard at ``/api/v1/ui`` (issue #188).

Acceptance criteria from the issue, as tests: the page shows an upload
widget, a scheme picker listing every bundled profile, and a Generate
button; dropping a valid CSV and generating yields the XML for
download. Plus the guard rails the page relies on: size cap, supported
suffixes, API-key enforcement, and the ``PAIN001_UI_DISABLED`` switch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pain001 import __version__
from pain001.api import ui as ui_module
from pain001.api.app import app
from pain001.constants import TEMPLATES_DIR, valid_xml_types
from pain001.validation.schemes import PROFILES

client = TestClient(app)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_CSV = (TEMPLATES_DIR / "pain.001.001.03" / "template.csv").read_text(
    encoding="utf-8"
)
DUPLICATES_CSV = (ROOT / "tests" / "data" / "duplicate_rows.csv").read_text(
    encoding="utf-8"
)


def _rows_from_csv(text: str) -> list[dict[str, str]]:
    """Parse ``text`` the way the browser never has to (test helper)."""
    import csv
    import io

    return list(csv.DictReader(io.StringIO(text)))


def _payload(**overrides: object) -> dict[str, object]:
    """Return a dashboard payload for the bundled sample CSV."""
    body: dict[str, object] = {
        "filename": "payments.csv",
        "content": TEMPLATE_CSV,
        "message_type": "pain.001.001.03",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------
def test_page_is_served_under_both_prefixes() -> None:
    """``/api/v1/ui`` is canonical; ``/api/ui`` is the legacy alias."""
    for path in ("/api/v1/ui", "/api/ui"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith("text/html")
        assert "<!doctype html>" in response.text.lower()


def test_page_shows_upload_widget_scheme_picker_and_generate_button() -> None:
    """Criterion 1: the widgets the issue names are all on the page."""
    text = client.get("/api/v1/ui").text
    assert 'type="file"' in text
    assert 'id="drop"' in text
    assert 'id="generate"' in text
    assert 'id="validate"' in text
    assert 'id="download"' in text
    for name in PROFILES:
        assert name in text, f"scheme picker omits {name}"
    for message_type in valid_xml_types:
        assert message_type in text, (
            f"message-type picker omits {message_type}"
        )


def test_page_embeds_the_build_version_and_no_external_assets() -> None:
    """One file, no framework, no CDN: nothing to fetch but the API."""
    text = client.get("/api/v1/ui").text
    assert f"v{__version__}" in text
    assert "<script src=" not in text
    assert '<link rel="stylesheet"' not in text
    assert "__MESSAGE_TYPES__" not in text
    assert "__SCHEMES__" not in text
    assert json.dumps(list(PROFILES)) in text


def test_page_is_hidden_from_the_openapi_schema_but_endpoints_are_not() -> (
    None
):
    """The HTML page is not an API; its two JSON endpoints are."""
    paths = app.openapi()["paths"]
    assert "/api/v1/ui" not in paths
    assert "/api/v1/ui/validate" in paths
    assert "/api/v1/ui/generate" in paths
    schemas = app.openapi()["components"]["schemas"]
    assert "UiFilePayload" in schemas
    assert "UiGenerateResponse" in schemas


# ---------------------------------------------------------------------------
# The switch and the lock
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_ui_disabled_hides_page_and_endpoints(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """``PAIN001_UI_DISABLED`` takes the whole surface offline with 404s."""
    monkeypatch.setenv("PAIN001_UI_DISABLED", value)
    assert ui_module.is_ui_enabled() is False
    assert client.get("/api/v1/ui").status_code == 404
    assert (
        client.post("/api/v1/ui/validate", json=_payload()).status_code == 404
    )
    assert (
        client.post("/api/v1/ui/generate", json=_payload()).status_code == 404
    )


@pytest.mark.parametrize("value", ["", "0", "no", "off"])
def test_ui_enabled_unless_switched_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Anything but an affirmative value leaves the dashboard on."""
    monkeypatch.setenv("PAIN001_UI_DISABLED", value)
    assert ui_module.is_ui_enabled() is True
    assert client.get("/api/v1/ui").status_code == 200


def test_endpoints_honour_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dashboard endpoints are locked by ``PAIN001_API_KEY`` too."""
    monkeypatch.setenv("PAIN001_API_KEY", "secret-key")
    assert (
        client.post("/api/v1/ui/validate", json=_payload()).status_code == 401
    )
    ok = client.post(
        "/api/v1/ui/generate",
        json=_payload(),
        headers={"Authorization": "Bearer secret-key"},
    )
    assert ok.status_code == 200
    # The page itself stays reachable so the user can enter the key.
    assert client.get("/api/v1/ui").status_code == 200


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
def test_validate_accepts_the_bundled_sample() -> None:
    """The bundled CSV validates cleanly against schema and SEPA SCT."""
    response = client.post(
        "/api/v1/ui/validate", json=_payload(scheme="sepa-sct")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["total_rows"] == len(_rows_from_csv(TEMPLATE_CSV))
    assert body["valid_rows"] == body["total_rows"]
    assert body["errors"] == []
    assert body["scheme_violations"] == []


def test_validate_reports_scheme_violations_from_a_composed_spec() -> None:
    """Criterion from #183 met through the dashboard: composition works."""
    response = client.post(
        "/api/v1/ui/validate",
        json=_payload(
            content=DUPLICATES_CSV, scheme="sepa-sct,anti-duplicate"
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert {v["rule"] for v in body["scheme_violations"]} == {
        "DUP-CREDITOR-DATE"
    }


def test_validate_reports_schema_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema failures come back as field-level errors, not a 4xx."""

    class _Error:
        path = "payment_amount"
        message = "must be a number"
        value = "abc"

    class _FakeValidator:
        def __init__(self, message_type: str) -> None:
            self.message_type = message_type

        def validate_batch(self, rows: list[dict[str, object]]) -> tuple:
            return len(rows), len(rows) - 1, [(0, [_Error()])]

    monkeypatch.setattr(ui_module, "SchemaValidator", _FakeValidator)
    response = client.post("/api/v1/ui/validate", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert body["invalid_rows"] == 1
    assert body["errors"] == [
        {
            "field": "payment_amount",
            "message": "must be a number",
            "value": "abc",
        }
    ]


def test_validate_rejects_unknown_scheme() -> None:
    """An unknown profile anywhere in the spec is a 400 naming it."""
    response = client.post(
        "/api/v1/ui/validate", json=_payload(scheme="sepa-sct,nope")
    )
    assert response.status_code == 400
    assert "'nope'" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
def test_generate_returns_the_xml_inline_for_download() -> None:
    """Criterion 2: drop a valid CSV, click Generate, get the XML."""
    response = client.post(
        "/api/v1/ui/generate", json=_payload(scheme="sepa-sct")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["filename"] == "pain.001.001.03.xml"
    assert body["xml"].startswith("<?xml")
    assert "pain.001.001.03" in body["xml"]
    assert body["validation_errors"] == []
    assert body["scheme_violations"] == []


def test_generate_is_blocked_by_scheme_violations() -> None:
    """Duplicates stop generation; the findings explain why."""
    response = client.post(
        "/api/v1/ui/generate",
        json=_payload(content=DUPLICATES_CSV, scheme="anti-duplicate"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["xml"] is None
    assert "anti-duplicate" in body["message"]
    assert body["scheme_violations"]


def test_generate_is_blocked_by_schema_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Schema errors stop generation before the template is rendered."""

    class _Error:
        path = "creditor_name"
        message = "required"
        value = None

    class _FakeValidator:
        def __init__(self, message_type: str) -> None:
            self.message_type = message_type

        def validate_batch(self, rows: list[dict[str, object]]) -> tuple:
            return len(rows), 0, [(0, [_Error()])]

    monkeypatch.setattr(ui_module, "SchemaValidator", _FakeValidator)
    response = client.post("/api/v1/ui/generate", json=_payload())
    body = response.json()
    assert response.status_code == 200
    assert body["success"] is False
    assert "Validation failed" in body["message"]
    assert body["validation_errors"][0]["field"] == "creditor_name"


def test_generate_surfaces_rendering_failures_as_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A document that fails the XSD is reported, not a 500."""

    def _boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Generated XML failed validation against xsd")

    monkeypatch.setattr(ui_module, "generate_xml_string", _boom)
    response = client.post("/api/v1/ui/generate", json=_payload())
    assert response.status_code == 400
    assert "Generation failed" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Parsing guard rails
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "filename", ["payments.xlsx", "payments", "x.parquet"]
)
def test_unsupported_suffix_is_rejected(filename: str) -> None:
    """Only the text formats the page can read are accepted."""
    response = client.post(
        "/api/v1/ui/validate", json=_payload(filename=filename)
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_oversized_upload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The size cap answers 413 and points at the CLI."""
    monkeypatch.setattr(ui_module, "MAX_UPLOAD_BYTES", 16)
    response = client.post("/api/v1/ui/validate", json=_payload())
    assert response.status_code == 413
    assert "CLI" in response.json()["detail"]


def test_empty_csv_is_rejected() -> None:
    """A header with no rows has nothing to validate."""
    response = client.post(
        "/api/v1/ui/validate",
        json=_payload(content=TEMPLATE_CSV.splitlines()[0] + "\n"),
    )
    assert response.status_code == 400
    assert "no payment rows" in response.json()["detail"]


def test_rows_failing_loader_validation_are_rejected() -> None:
    """A CSV with the wrong columns is a 400, mirroring the loaders."""
    response = client.post(
        "/api/v1/ui/validate", json=_payload(content="foo,bar\n1,2\n")
    )
    assert response.status_code == 400


def test_json_object_and_array_are_both_accepted() -> None:
    """A single object is one row; an array is many."""
    rows = _rows_from_csv(TEMPLATE_CSV)
    single = client.post(
        "/api/v1/ui/validate",
        json=_payload(filename="p.json", content=json.dumps(rows[0])),
    )
    assert single.status_code == 200
    assert single.json()["total_rows"] == 1
    many = client.post(
        "/api/v1/ui/validate",
        json=_payload(filename="p.json", content=json.dumps(rows)),
    )
    assert many.status_code == 200
    assert many.json()["total_rows"] == len(rows)


def test_jsonl_is_parsed_line_by_line_skipping_blanks() -> None:
    """JSON Lines: one object per line, blank lines ignored."""
    rows = _rows_from_csv(TEMPLATE_CSV)
    text = "\n\n".join(json.dumps(r) for r in rows) + "\n\n"
    response = client.post(
        "/api/v1/ui/validate",
        json=_payload(filename="p.jsonl", content=text),
    )
    assert response.status_code == 200
    assert response.json()["total_rows"] == len(rows)


@pytest.mark.parametrize(
    ("filename", "content", "fragment"),
    [
        ("p.json", "{not json", "Invalid JSON"),
        ("p.json", "42", "object or an array"),
        ("p.json", "[1, 2]", "JSON object"),
        ("p.jsonl", '{"a": 1}\n{oops\n', "line 2"),
        ("p.jsonl", "[1]\n", "JSON object"),
        ("p.json", "[]", "no payment rows"),
    ],
)
def test_malformed_json_inputs_are_400s(
    filename: str, content: str, fragment: str
) -> None:
    """Every malformed shape is explained, never a 500."""
    response = client.post(
        "/api/v1/ui/validate",
        json=_payload(filename=filename, content=content),
    )
    assert response.status_code == 400, response.text
    assert fragment in response.json()["detail"]
