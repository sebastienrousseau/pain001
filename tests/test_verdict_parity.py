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

"""One verdict per input on every surface: CLI, Python and REST.

Each case is the bundled pain.001.001.03 sample with one value changed.
Every surface either accepts it or refuses it; none may disagree.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

import pain001
from pain001.api.app import app
from pain001.cli.cli import cli
from pain001.constants import TEMPLATES_DIR
from pain001.core.core import process_files

MESSAGE_TYPE = "pain.001.001.03"
SAMPLE = TEMPLATES_DIR / MESSAGE_TYPE / "template.csv"
TEMPLATE = TEMPLATES_DIR / MESSAGE_TYPE / "template.xml"
SCHEMA = TEMPLATES_DIR / MESSAGE_TYPE / f"{MESSAGE_TYPE}.xsd"

client = TestClient(app)

# (case id, column changed in the first row, new value, accepted?)
CASES = [
    ("sample", None, None, True),
    ("currency-euro", "currency", "EURO", False),
    ("currency-lowercase", "currency", "eur", False),
    ("bad-iban", "creditor_account_IBAN", "DE00000000000000000000", False),
    ("bad-bic", "debtor_agent_BIC", "NOTABIC", False),
    ("amount-not-decimal", "payment_amount", "abc", False),
    ("missing-debtor-name", "debtor_name", "", False),
]


def _write_case(directory: Path, column: str | None, value: str | None) -> str:
    """Write the sample with ``column`` of its first row set to ``value``."""
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if column is not None:
        rows[1][rows[0].index(column)] = value or ""
    path = directory / "payments.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return str(path)


def _cli_validate(data: str, _out: Path) -> bool:
    result = CliRunner().invoke(
        cli, ["validate", "-t", MESSAGE_TYPE, "-d", data]
    )
    assert result.exit_code in (0, 1), result.output
    return result.exit_code == 0


def _cli_generate(data: str, out: Path) -> bool:
    result = CliRunner().invoke(
        cli, ["generate", "-t", MESSAGE_TYPE, "-d", data, "-o", str(out)]
    )
    assert result.exit_code in (0, 1), result.output
    return result.exit_code == 0


def _process_files(data: str, out: Path) -> bool:
    try:
        process_files(
            MESSAGE_TYPE,
            str(TEMPLATE),
            str(SCHEMA),
            data,
            output_path=str(out / "out.xml"),
        )
    except pain001.PaymentValidationError:
        return False
    return True


def _python_validate(data: str, _out: Path) -> bool:
    return pain001.validate(data, MESSAGE_TYPE).is_valid


def _python_generate(data: str, out: Path) -> bool:
    try:
        pain001.generate(data, MESSAGE_TYPE, output_dir=out)
    except pain001.PaymentValidationError:
        return False
    return True


def _body(data: str, out: Path) -> dict[str, str]:
    return {
        "file_path": data,
        "data_source": "csv",
        "message_type": MESSAGE_TYPE,
        "output_dir": str(out),
    }


def _rest_validate(data: str, out: Path) -> bool:
    response = client.post("/api/v1/validate", json=_body(data, out))
    if response.status_code == 400:
        return False
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["invalid_rows"] == body["total_rows"] - body["valid_rows"]
    return bool(body["is_valid"])


def _rest_generate(data: str, out: Path) -> bool:
    response = client.post("/api/v1/generate", json=_body(data, out))
    assert response.status_code in (200, 400, 422), response.text
    return response.status_code == 200 and response.json()["success"]


SURFACES: dict[str, Callable[[str, Path], bool]] = {
    "cli-validate": _cli_validate,
    "cli-generate": _cli_generate,
    "process_files": _process_files,
    "python-validate": _python_validate,
    "python-generate": _python_generate,
    "rest-validate": _rest_validate,
    "rest-generate": _rest_generate,
}


@pytest.mark.parametrize(
    ("column", "value", "accepted"),
    [pytest.param(c, v, a, id=i) for i, c, v, a in CASES],
)
def test_every_surface_gives_the_same_verdict(
    tmp_path: Path, column: str | None, value: str | None, accepted: bool
) -> None:
    data = _write_case(tmp_path, column, value)
    verdicts = {}
    for name, surface in SURFACES.items():
        out = tmp_path / name
        out.mkdir()
        verdicts[name] = surface(data, out)
    assert verdicts == dict.fromkeys(SURFACES, accepted)


@pytest.mark.parametrize(
    ("column", "value"),
    [pytest.param(c, v, id=i) for i, c, v, _ in CASES],
)
def test_ui_generate_answers_the_status_rest_generate_does(
    tmp_path: Path, column: str | None, value: str | None
) -> None:
    """The dashboard's generate and ``/generate`` share each status."""
    data = _write_case(tmp_path, column, value)
    rest = client.post("/api/v1/generate", json=_body(data, tmp_path))
    ui = client.post(
        "/api/v1/ui/generate",
        json={
            "filename": "payments.csv",
            "content": Path(data).read_text(encoding="utf-8"),
            "message_type": MESSAGE_TYPE,
        },
    )
    assert ui.status_code == rest.status_code, ui.text


def test_rest_validate_counts_the_refused_row(tmp_path: Path) -> None:
    data = _write_case(tmp_path, "currency", "EURO")
    response = client.post("/api/v1/validate", json=_body(data, tmp_path))
    body = response.json()
    assert (body["total_rows"], body["valid_rows"], body["invalid_rows"]) == (
        4,
        3,
        1,
    )


def test_ui_validate_refuses_what_ui_generate_refuses(tmp_path: Path) -> None:
    """Two payment blocks in one upload: neither UI route accepts it."""
    data = Path(_write_case(tmp_path, None, None))
    rows = list(csv.reader(data.open(encoding="utf-8", newline="")))
    rows[2][rows[0].index("debtor_name")] = "Other Corp"
    with data.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    body = {
        "filename": "payments.csv",
        "content": data.read_text(encoding="utf-8"),
        "message_type": MESSAGE_TYPE,
    }
    validated = client.post("/api/v1/ui/validate", json=body)
    generated = client.post("/api/v1/ui/generate", json=body)
    assert generated.status_code == 400
    assert validated.status_code == 400
    assert "one payment information block" in validated.json()["detail"]


@pytest.mark.parametrize("command", ["validate", "generate"])
def test_json_result_reports_the_schema_refusal(
    tmp_path: Path, command: str
) -> None:
    """``--format json`` carries the refusal: ok false, P001-E030, exit 1."""
    data = _write_case(tmp_path, "currency", "EURO")
    args = [command, "-t", MESSAGE_TYPE, "-d", data, "--format", "json"]
    if command == "generate":
        args += ["-o", str(tmp_path / "out")]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1
    body = json.loads(result.stdout)
    assert body["ok"] is False
    assert "line 2, column currency" in body["error"]
    assert "P001-E030" in body["error"]
    assert body["files"] == []
