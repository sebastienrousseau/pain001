# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``POST /api/v1/check``: the check engine over REST."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from pain001 import check  # noqa: E402
from pain001.api.app import app  # noqa: E402
from pain001.check import MAX_CHECK_BYTES  # noqa: E402

client = TestClient(app)
GOOD = (
    Path(check.__file__).parent
    / "corpus"
    / "data"
    / "coverage"
    / "pain.001.001.09"
    / "01-transfer-every-element.xml"
).read_text(encoding="utf-8")


def test_a_valid_document_passes() -> None:
    response = client.post("/api/v1/check", json={"xml": GOOD})
    assert response.status_code == 200
    body = response.json()
    assert body["message_type"] == "pain.001.001.09"
    assert body["passed"] is True
    assert body["rungs"] == ["xsd", "mdr"]
    assert body["findings"] == []


def test_the_legacy_prefix_answers_too() -> None:
    assert client.post("/api/check", json={"xml": GOOD}).status_code == 200


def test_a_failing_rung_is_a_200_with_findings() -> None:
    bad = GOOD.replace("<NbOfTxs>", "<Foo>x</Foo><NbOfTxs>", 1)
    response = client.post("/api/v1/check", json={"xml": bad})
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["findings"][0]["rung"] == "xsd"
    assert (
        body["findings"][0]["location"] == "/Document/CstmrCdtTrfInitn/GrpHdr"
    )


def test_scheme_and_schematron_rungs_run() -> None:
    response = client.post(
        "/api/v1/check",
        json={"xml": GOOD, "scheme": "sepa-sct", "schematron": "sepa"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rungs"] == ["xsd", "mdr", "scheme", "schematron"]
    assert any(f["rule"] == "SEPA-CHRGBR" for f in body["findings"])


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"xml": "<root/>"}, "not a pain.001 or pain.008 Document"),
        ({"xml": GOOD, "scheme": "no-such-scheme"}, "no-such-scheme"),
        (
            {"xml": '<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>'},
            "DTDs and entities are not allowed",
        ),
    ],
)
def test_a_document_that_cannot_be_checked_is_a_422(
    payload: dict[str, str], detail: str
) -> None:
    response = client.post("/api/v1/check", json=payload)
    assert response.status_code == 422
    assert detail in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"xml": ""},
        {"xml": "<x/>" * (MAX_CHECK_BYTES // 4 + 1)},
        {"xml": "<x/>", "scheme": "../etc"},
        {"xml": "<x/>", "schematron": "/etc/passwd"},
        {"xml": "<x/>", "schematron": "rules.sch"},
    ],
    ids=["empty", "oversized", "scheme-path", "abs-path", "sch-file"],
)
def test_the_request_model_refuses_paths_and_sizes(
    payload: dict[str, str],
) -> None:
    assert client.post("/api/v1/check", json=payload).status_code == 422


def test_a_preset_is_accepted_in_any_case() -> None:
    response = client.post(
        "/api/v1/check", json={"xml": GOOD, "schematron": "SEPA"}
    )
    assert response.status_code == 200


def test_the_route_is_locked_by_the_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAIN001_API_KEY", "secret-key")
    assert client.post("/api/v1/check", json={"xml": GOOD}).status_code == 401
    response = client.post(
        "/api/v1/check",
        json={"xml": GOOD},
        headers={"Authorization": "Bearer secret-key"},
    )
    assert response.status_code == 200


def test_the_route_is_in_the_openapi_schema() -> None:
    assert "/api/v1/check" in app.openapi()["paths"]
