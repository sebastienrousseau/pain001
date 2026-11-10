# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Run the SDK conformance kit against the in-process REST app.

Every pain001 SDK runs ``conformance/cases.json`` against a live
``pain001 serve``; this proves each case holds for the server itself,
and that ``conformance/openapi.json`` matches the app. The small runner
below is the reference the SDK runners port.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from pain001.api.app import app  # noqa: E402

KIT = Path(__file__).resolve().parent.parent / "conformance"
CASES = json.loads((KIT / "cases.json").read_text(encoding="utf-8"))["cases"]
_TYPES = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: (
        isinstance(v, (int, float)) and not isinstance(v, bool)
    ),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _resolve(body: Any) -> Any:
    """Replace ``{"$file": ...}`` with that fixture's text, recursively."""
    if isinstance(body, dict):
        if set(body) == {"$file"}:
            return (KIT / body["$file"]).read_text(encoding="utf-8")
        return {key: _resolve(value) for key, value in body.items()}
    if isinstance(body, list):
        return [_resolve(item) for item in body]
    return body


def _pointer(document: Any, pointer: str) -> Any:
    """RFC 6901 JSON Pointer lookup; raises KeyError when absent."""
    if pointer == "":
        return document
    value = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not token.isdigit() or int(token) >= len(value):
                raise KeyError(pointer)
            value = value[int(token)]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise KeyError(pointer)
    return value


def run_case(client: TestClient, case: dict[str, Any]) -> list[str]:
    """Send one case and return the failed expectations (empty = pass)."""
    body = _resolve(case.get("body"))
    response = client.request(case["method"], case["path"], json=body)
    expect = case["expect"]
    failures = []
    if response.status_code != expect["status"]:
        failures.append(f"status {response.status_code} != {expect['status']}")
        return failures
    document = response.json()
    for pointer, wanted in expect.get("equals", {}).items():
        try:
            if _pointer(document, pointer) != wanted:
                failures.append(f"{pointer} != {wanted!r}")
        except KeyError:
            failures.append(f"{pointer} missing")
    for pointer, kind in expect.get("types", {}).items():
        try:
            if not _TYPES[kind](_pointer(document, pointer)):
                failures.append(f"{pointer} is not {kind}")
        except KeyError:
            failures.append(f"{pointer} missing")
    for pointer, needles in expect.get("contains", {}).items():
        try:
            value = _pointer(document, pointer)
        except KeyError:
            failures.append(f"{pointer} missing")
            continue
        if not isinstance(value, str):
            failures.append(f"{pointer} is not a string")
            continue
        failures.extend(
            f"{pointer} lacks {n!r}" for n in needles if n not in value
        )
    return failures


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_every_case_holds_for_the_server(case):
    assert run_case(TestClient(app), case) == []


def test_the_openapi_snapshot_matches_the_app():
    spec = importlib.util.spec_from_file_location(
        "build_conformance_openapi",
        KIT.parent / "scripts" / "build_conformance_openapi.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0
    # The snapshot's kit version never leaks into the app's own document.
    from pain001 import __version__  # noqa: PLC0415

    assert app.openapi()["info"]["version"] == __version__


def test_the_runner_reports_each_kind_of_failure():
    """The reference runner fails loudly, so SDK ports have a model."""
    client = TestClient(app)
    case = {
        "id": "x",
        "method": "GET",
        "path": "/api/v1/health",
        "expect": {
            "status": 200,
            "equals": {"/status": "down", "/nope": 1},
            "types": {"/status": "integer", "/gone": "string"},
            "contains": {"/status": ["zzz"], "/version": [], "/none": ["a"]},
        },
    }
    case["expect"]["contains"]["/version"] = ["0.0."]
    failures = run_case(client, case)
    assert "/status != 'down'" in failures and "/nope missing" in failures
    assert "/status is not integer" in failures and "/gone missing" in failures
    assert "/status lacks 'zzz'" in failures and "/none missing" in failures
    assert run_case(client, {**case, "expect": {"status": 404}}) == [
        "status 200 != 404"
    ]
    list_case = {
        "id": "l",
        "method": "GET",
        "path": "/api/v1/faces",
        "expect": {
            "status": 200,
            "equals": {"/9/name": "x", "/a": 1},
            "contains": {"/0": ["x"]},
        },
    }
    assert run_case(client, list_case) == [
        "/9/name missing",
        "/a missing",
        "/0 is not a string",
    ]
    assert _resolve([{"$file": "fixtures/bad-iban.pain.001.001.09.csv"}])[
        0
    ].startswith("id,")
    assert _pointer({"a/b": {"~": 1}}, "/a~1b/~0") == 1
