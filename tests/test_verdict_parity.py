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

Each case is a bundled sample with one value changed, or with columns
removed. Every surface either accepts it or refuses it; none may
disagree.
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
from pain001.core.core import process_files, process_files_streaming

MESSAGE_TYPE = "pain.001.001.03"

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

#: Columns every bundled schema describes but some types never require.
#: Before the loader knew the message type it demanded all of them.
DEFAULTED = (
    "service_level_code",
    "forwarding_agent_BIC",
    "payment_method",
    "charge_bearer",
)

# (case id, message type, columns removed, accepted?)
CONTRACT_CASES = [
    ("v09-without-defaulted-columns", "pain.001.001.09", DEFAULTED, True),
    ("v03-without-defaulted-columns", "pain.001.001.03", DEFAULTED, True),
    ("v08-without-forwarding-agent", "pain.001.001.08", DEFAULTED[1:2], True),
    (
        "v09-without-debtor-account",
        "pain.001.001.09",
        ("debtor_account_IBAN",),
        False,
    ),
    (
        "v09-without-creditor-agent",
        "pain.001.001.09",
        ("creditor_agent_BIC",),
        False,
    ),
    ("v09-without-debtor-name", "pain.001.001.09", ("debtor_name",), False),
]


def _write_case(
    directory: Path,
    column: str | None,
    value: str | None,
    message_type: str = MESSAGE_TYPE,
    removed: tuple[str, ...] = (),
) -> str:
    """Write the sample with ``column`` of its first row set to ``value``.

    The columns in ``removed`` are left out of the file altogether.
    """
    sample = TEMPLATES_DIR / message_type / "template.csv"
    with sample.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if column is not None:
        rows[1][rows[0].index(column)] = value or ""
    kept = [i for i, name in enumerate(rows[0]) if name not in removed]
    rows = [[row[i] for i in kept] for row in rows]
    path = directory / "payments.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return str(path)


def _cli_validate(data: str, _out: Path, mt: str = MESSAGE_TYPE) -> bool:
    result = CliRunner().invoke(cli, ["validate", "-t", mt, "-d", data])
    assert result.exit_code in (0, 1), result.output
    return result.exit_code == 0


def _cli_generate(data: str, out: Path, mt: str = MESSAGE_TYPE) -> bool:
    result = CliRunner().invoke(
        cli, ["generate", "-t", mt, "-d", data, "-o", str(out)]
    )
    assert result.exit_code in (0, 1), result.output
    return result.exit_code == 0


def _paths(mt: str) -> tuple[str, str]:
    """The bundled template and XSD of ``mt``."""
    base = TEMPLATES_DIR / mt
    return str(base / "template.xml"), str(base / f"{mt}.xsd")


def _process_files(data: str, out: Path, mt: str = MESSAGE_TYPE) -> bool:
    try:
        process_files(mt, *_paths(mt), data, output_path=str(out / "out.xml"))
    except pain001.PaymentValidationError:
        return False
    return True


def _process_files_streaming(
    data: str, out: Path, mt: str = MESSAGE_TYPE
) -> bool:
    try:
        process_files_streaming(
            mt, *_paths(mt), data, chunk_size=2, output_dir=str(out)
        )
    except pain001.PaymentValidationError:
        return False
    return True


def _python_validate(data: str, _out: Path, mt: str = MESSAGE_TYPE) -> bool:
    return pain001.validate(data, mt).is_valid


def _python_validate_rows(
    data: str, _out: Path, mt: str = MESSAGE_TYPE
) -> bool:
    with Path(data).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return pain001.validate(rows, mt).is_valid


def _python_generate(data: str, out: Path, mt: str = MESSAGE_TYPE) -> bool:
    try:
        pain001.generate(data, mt, output_dir=out)
    except pain001.PaymentValidationError:
        return False
    return True


def _body(data: str, out: Path, mt: str = MESSAGE_TYPE) -> dict[str, str]:
    return {
        "file_path": data,
        "data_source": "csv",
        "message_type": mt,
        "output_dir": str(out),
    }


def _rest_validate(data: str, out: Path, mt: str = MESSAGE_TYPE) -> bool:
    response = client.post("/api/v1/validate", json=_body(data, out, mt))
    if response.status_code == 400:
        return False
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["invalid_rows"] == body["total_rows"] - body["valid_rows"]
    return bool(body["is_valid"])


def _rest_generate(data: str, out: Path, mt: str = MESSAGE_TYPE) -> bool:
    response = client.post("/api/v1/generate", json=_body(data, out, mt))
    assert response.status_code in (200, 400, 422), response.text
    return response.status_code == 200 and response.json()["success"]


def _upload(data: str, mt: str) -> dict[str, str]:
    return {
        "filename": "payments.csv",
        "content": Path(data).read_text(encoding="utf-8"),
        "message_type": mt,
    }


def _ui_validate(data: str, _out: Path, mt: str = MESSAGE_TYPE) -> bool:
    response = client.post("/api/v1/ui/validate", json=_upload(data, mt))
    assert response.status_code in (200, 400), response.text
    return response.status_code == 200 and response.json()["is_valid"]


def _ui_generate(data: str, _out: Path, mt: str = MESSAGE_TYPE) -> bool:
    response = client.post("/api/v1/ui/generate", json=_upload(data, mt))
    assert response.status_code in (200, 400), response.text
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


#: Every surface, plus the ones only a whole-file check can reach.
CONTRACT_SURFACES: dict[str, Callable[[str, Path, str], bool]] = {
    **SURFACES,
    "process_files_streaming": _process_files_streaming,
    "python-validate-rows": _python_validate_rows,
    "ui-validate": _ui_validate,
    "ui-generate": _ui_generate,
}


@pytest.mark.parametrize(
    ("message_type", "removed", "accepted"),
    [pytest.param(t, r, a, id=i) for i, t, r, a in CONTRACT_CASES],
)
def test_the_row_contract_is_the_message_types_own(
    tmp_path: Path, message_type: str, removed: tuple[str, ...], accepted: bool
) -> None:
    """A column only another type requires is not demanded.

    Until 0.0.87 the loader checked rows against every column any
    bundled schema describes, so a pain.001.001.09 file without
    ``payment_method`` or ``charge_bearer`` (which have defaults) was
    refused, though that type's schema does not require them. A column
    generation needs (a debtor account) is still refused everywhere.
    """
    data = _write_case(tmp_path, None, None, message_type, removed)
    verdicts = _contract_verdicts(tmp_path, data, message_type)
    assert verdicts == dict.fromkeys(CONTRACT_SURFACES, accepted)


def _contract_verdicts(
    tmp_path: Path, data: str, message_type: str
) -> dict[str, bool]:
    """Each contract surface's verdict on ``data``."""
    verdicts = {}
    for name, surface in CONTRACT_SURFACES.items():
        out = tmp_path / name
        out.mkdir()
        verdicts[name] = surface(data, out, message_type)
    return verdicts


def test_an_account_number_stands_in_for_the_iban(tmp_path: Path) -> None:
    """Generation takes a debtor account number; so does validation.

    The every-column contract demanded ``debtor_account_IBAN``, so a
    file that names the account by number was refused before generation
    could see it.
    """
    message_type = "pain.001.001.09"
    data = Path(_write_case(tmp_path, None, None, message_type))
    with data.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    column = rows[0].index("debtor_account_IBAN")
    rows[0][column] = "debtor_account_number"
    for row in rows[1:]:
        row[column] = "12345678"
    with data.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    verdicts = _contract_verdicts(tmp_path, str(data), message_type)
    assert verdicts == dict.fromkeys(CONTRACT_SURFACES, True)


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
