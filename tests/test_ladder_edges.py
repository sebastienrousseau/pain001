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

"""Validation-ladder defaults, policy reading, record fixes, schema lookups.

Each test pins a default or a bound a caller relies on without passing
it: line numbers counted from the first row, identifier checks on by
default, the policy read cut one byte past the cap, the wording when
the ``rules`` extra is missing, and the refusals of the record fixer.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from pain001.constants import TEMPLATES_DIR
from pain001.exceptions import PaymentValidationError
from pain001.validation.corrections import suggest_record_fix
from pain001.validation.ladder import (
    check_scheme,
    load_valid_chunks,
    read_policy,
    require_schema_valid,
)
from pain001.validation.schema_validator import SchemaValidator

MESSAGE_TYPE = "pain.001.001.03"
SAMPLE = TEMPLATES_DIR / MESSAGE_TYPE / "template.csv"


def _rows(**changes: str) -> list[dict[str, Any]]:
    """The bundled sample's rows with ``changes`` in every row."""
    with SAMPLE.open(encoding="utf-8", newline="") as handle:
        return [dict(row, **changes) for row in csv.DictReader(handle)]


def _write(path: Path, rows: list[dict[str, Any]]) -> str:
    """Write ``rows`` as CSV at ``path`` and return the path."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def test_schema_refusal_defaults_count_lines_from_one() -> None:
    """Without a start or first line, row 1 is line 2; the value is hidden."""
    rows = _rows()
    rows[1]["currency"] = "EURO"
    with pytest.raises(PaymentValidationError) as caught:
        require_schema_valid(rows, MESSAGE_TYPE)
    assert str(caught.value).startswith(
        f"{MESSAGE_TYPE} schema validation failed (1 problem):"
    )
    [issue] = caught.value.errors
    assert (issue.line, issue.column) == (2, "currency")
    assert issue.message == "the value does not match '^[A-Z]{3}$'"
    assert "EURO" not in issue.message


def test_chunk_lines_keep_counting_across_every_chunk(tmp_path: Path) -> None:
    """With one-row chunks, the fourth row is still line 5 of the input."""
    rows = _rows()
    rows[3]["currency"] = "EURO"
    chunks = load_valid_chunks(
        _write(tmp_path / "p.csv", rows), MESSAGE_TYPE, chunk_size=1
    )
    assert [len(next(chunks)) for _ in range(3)] == [1, 1, 1]
    with pytest.raises(PaymentValidationError) as caught:
        next(chunks)
    assert caught.value.errors[0].line == 5


def test_chunks_check_identifiers_by_default(tmp_path: Path) -> None:
    """A bad IBAN stops chunked loading unless the checks are turned off."""
    rows = _rows(debtor_account_IBAN="DE00512108001245126162")
    path = _write(tmp_path / "p.csv", rows)
    assert len(list(load_valid_chunks(path, MESSAGE_TYPE, 4, False))) == 1
    with pytest.raises(Exception, match="DE00512108001245126162|IBAN"):
        list(load_valid_chunks(path, MESSAGE_TYPE, 4))


def test_read_policy_stops_one_byte_past_the_cap(tmp_path: Path) -> None:
    """A huge policy is read only far enough to be refused."""
    from pain001.validation.policy import MAX_POLICY_BYTES

    policy = tmp_path / "policy.yaml"
    policy.write_text("#" * (MAX_POLICY_BYTES + 10), encoding="utf-8")
    assert len(read_policy(policy)) == MAX_POLICY_BYTES + 1


def test_the_missing_rules_extra_is_named_exactly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both policy entry points say which extra to install."""
    monkeypatch.setitem(sys.modules, "pain001.validation.policy", None)
    policy = tmp_path / "policy.yaml"
    policy.write_text("[]\n", encoding="utf-8")
    for call in (
        lambda: check_scheme(_rows(), MESSAGE_TYPE, rules="[]"),
        lambda: read_policy(policy),
    ):
        with pytest.raises(ValueError) as caught:
            call()
        assert str(caught.value) == "Custom rules require 'pain001[rules]'."


def test_check_scheme_composes_the_scheme_with_the_policy() -> None:
    """A scheme and a policy run together; no scheme at all is refused."""
    rules = (
        "- {id: BIG, where: 'payment_amount > decimal(\"1\")', "
        "severity: warning, message: Big.}\n"
    )
    result = check_scheme(_rows(), MESSAGE_TYPE, "sepa-sct", rules)
    assert result.profile == "sepa-sct,custom"
    assert "BIG" in {v.rule for v in result.violations}
    with pytest.raises(ValueError, match=r"^Unknown scheme profile ''\."):
        check_scheme(_rows(), MESSAGE_TYPE)


def test_record_fixes_refuse_what_they_cannot_derive() -> None:
    """A non-ISO date with no single reading, and an unnamed field."""
    record = {"requested_execution_date": "2026115"}
    error = {"field": "requested_execution_date", "rule": "DATE-FORMAT"}
    assert suggest_record_fix(record, error) == {
        "patches": [],
        "cannot_autofix": "no_unambiguous_fix",
    }
    assert suggest_record_fix({}, {"rule": "DATE-FORMAT"}) == {
        "patches": [],
        "cannot_autofix": "invalid_field",
    }


def test_schema_lookups_tolerate_missing_sections(tmp_path: Path) -> None:
    """No required list, no properties, or a non-object property: empty."""
    schema_file = tmp_path / f"{MESSAGE_TYPE}.schema.json"
    schema_file.write_text(
        json.dumps({"required": None, "properties": {"x": "string"}}),
        encoding="utf-8",
    )
    validator = SchemaValidator(MESSAGE_TYPE, schema_dir=tmp_path)
    assert validator.get_required_fields() == []
    assert validator.get_field_schema("x") is None
    schema_file.write_text("{}", encoding="utf-8")
    bare = SchemaValidator(MESSAGE_TYPE, schema_dir=tmp_path)
    assert bare.get_required_fields() == []
    assert bare.get_field_schema("x") is None
