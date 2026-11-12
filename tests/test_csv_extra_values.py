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

"""A CSV row with more values than the header has columns is refused."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pain001
from pain001.api.app import app
from pain001.constants import TEMPLATES_DIR
from pain001.data.loader import load_payment_data
from pain001.exceptions import IssueCode, PaymentValidationError

SAMPLE = TEMPLATES_DIR / "pain.001.001.03" / "template.csv"


def _extra_value_file(tmp_path: Path) -> str:
    """Write the sample with one stray value at the end of its 2nd row."""
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    lines[2] += ",stray"
    path = tmp_path / "payments.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_the_loader_names_the_line(tmp_path: Path) -> None:
    with pytest.raises(PaymentValidationError) as caught:
        load_payment_data(_extra_value_file(tmp_path))
    [issue] = caught.value.errors
    assert (issue.line, issue.column, issue.code) == (
        3,
        None,
        IssueCode.EXTRA_VALUES,
    )
    assert "stray" not in str(caught.value)


def test_python_validate_reports_it(tmp_path: Path) -> None:
    report = pain001.validate(_extra_value_file(tmp_path))
    assert not report.is_valid
    assert report.issues[0].code == IssueCode.EXTRA_VALUES


@pytest.mark.parametrize("route", ["/api/v1/validate", "/api/v1/generate"])
def test_rest_answers_400_not_500(tmp_path: Path, route: str) -> None:
    response = TestClient(app).post(
        route,
        json={
            "file_path": _extra_value_file(tmp_path),
            "data_source": "csv",
            "message_type": "pain.001.001.03",
            "output_dir": str(tmp_path),
        },
    )
    assert response.status_code == 400, response.text
    assert "P001-E002" in response.json()["detail"]
