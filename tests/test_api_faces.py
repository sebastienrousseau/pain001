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

"""Faces over REST: ``GET /api/v1/faces`` and ``POST /api/v1/faces/{face}``."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pain001.api.app import app
from pain001.corpus import get_file, list_files
from pain001.faces import list_supported_faces, project_face

client = TestClient(app)

SALARY_09 = get_file("de.sepa.sct-salary", "pain.001.001.09")
EVERY_ELEMENT_09 = next(
    f.path
    for f in list_files("coverage")
    if f.version == "pain.001.001.09"
    and f.path.name.startswith("01-transfer-every-element")
).read_text(encoding="utf-8")


@pytest.mark.parametrize("prefix", ["/api/v1", "/api"])
def test_list_faces_under_both_prefixes(prefix: str) -> None:
    """The list is the library's, served under the canonical and legacy prefix."""
    response = client.get(f"{prefix}/faces")
    assert response.status_code == 200
    assert response.json() == list_supported_faces()


def test_project_matches_the_library() -> None:
    """The response is the library's result, payload and loss report."""
    response = client.post(
        "/api/v1/faces/berlin_group", json={"xml": SALARY_09}
    )
    assert response.status_code == 200
    expected = project_face(SALARY_09, face="berlin_group").to_dict()
    assert response.json() == expected
    assert response.json()["loss_report"]["unmapped_paths"]


def test_project_with_bindings_and_explicit_version() -> None:
    """A ConsentId binding turns the UK body into OBWriteDomestic2."""
    response = client.post(
        "/api/v1/faces/uk_open_banking",
        json={
            "xml": EVERY_ELEMENT_09,
            "version": "pain.001.001.09",
            "bindings": {"ConsentId": "consent-api-1"},
        },
    )
    assert response.status_code == 200
    data = response.json()["payload"]["Data"]
    assert data["ConsentId"] == "consent-api-1"
    assert "Initiation" in data


def test_unknown_face_is_404() -> None:
    """A face name that is not registered is not found."""
    response = client.post("/api/v1/faces/nope", json={"xml": SALARY_09})
    assert response.status_code == 404
    assert "berlin_group" in response.json()["detail"]


@pytest.mark.parametrize(
    ("face", "body", "reason"),
    [
        ("uk_open_banking", {"xml": SALARY_09}, "uk_open_banking"),
        (
            "berlin_group",
            {"xml": SALARY_09, "bindings": {"ConsentId": "c"}},
            "unknown binding",
        ),
        ("iso_2018", {"xml": "/etc/passwd"}, "expected the pain.001 document"),
        (
            "iso_2018",
            {"xml": '<!DOCTYPE d [<!ENTITY a "a">]><d>&a;</d>'},
            "refused XML",
        ),
        ("iso_2018", {"xml": "<a><b></a>"}, "not well-formed XML"),
    ],
    ids=["refused", "binding", "path", "entity", "malformed"],
)
def test_refusals_are_422_with_the_reason(
    face: str, body: dict[str, object], reason: str
) -> None:
    """The face's own reason comes back; nothing is read from the server."""
    response = client.post(f"/api/v1/faces/{face}", json=body)
    assert response.status_code == 422
    assert reason in response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"xml": ""},
        {"xml": SALARY_09, "version": "pain.008.001.08"},
        {"xml": SALARY_09, "bindings": ["ConsentId"]},
    ],
    ids=["missing", "empty", "not-pain001", "bindings-list"],
)
def test_invalid_requests_fail_validation(body: dict[str, object]) -> None:
    """The request model rejects what the engine would never accept."""
    response = client.post("/api/v1/faces/iso_2018", json=body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_faces_honour_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both routes are locked by ``PAIN001_API_KEY``."""
    monkeypatch.setenv("PAIN001_API_KEY", "secret-key")
    assert client.get("/api/v1/faces").status_code == 401
    assert (
        client.post(
            "/api/v1/faces/iso_2018", json={"xml": SALARY_09}
        ).status_code
        == 401
    )
    ok = client.post(
        "/api/v1/faces/iso_2018",
        json={"xml": SALARY_09},
        headers={"Authorization": "Bearer secret-key"},
    )
    assert ok.status_code == 200


def test_openapi_documents_the_faces() -> None:
    """The routes, the tag and the response model are in the schema."""
    schema = app.openapi()
    assert {"/api/v1/faces", "/api/v1/faces/{face}"} <= set(schema["paths"])
    assert "Faces" in {tag["name"] for tag in schema["tags"]}
    assert "FaceResponse" in schema["components"]["schemas"]
    assert not any(path.startswith("/api/faces") for path in schema["paths"])
