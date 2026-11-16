# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Output paths, template reading, preparers and log lines, pinned exactly.

Mutation testing found that changing these details (an error message,
a warning's stack level, a file encoding, a slice bound) failed no
test. Each one is checked here directly.
"""

from __future__ import annotations

import contextvars
import io
import json
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jsonschema
import pytest

import pain001.security
from pain001.context.context import Context
from pain001.data.loader import load_payment_data
from pain001.db.load_db_data import sanitize_table_name
from pain001.exceptions import ConfigurationError, PaymentValidationError
from pain001.logging_schema import events
from pain001.logging_schema.context import get_request_id
from pain001.logging_schema.schema import Fields
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
from pain001.validation.schema_validator import SchemaValidator
from pain001.xml import _render, message_registry, publish

_TYPE = "pain.001.001.03"


def _rows() -> list[dict[str, Any]]:
    """The bundled pain.001.001.03 example rows."""
    bundle = DEFAULT_TEMPLATE_REGISTRY.get_template(_TYPE)
    return load_payment_data(str(bundle.example_data_path))


def test_the_deprecation_warning_points_two_frames_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The warning says why, and by default points at generate_xml's caller.

    The stack level is read from the ``warnings.warn`` call rather than
    from the warning's line number, so the check holds however many
    frames a wrapper (or a mutation tool's trampoline) adds.
    """
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        publish,
        "warnings",
        SimpleNamespace(warn=lambda *a, **k: calls.append((a, k))),
    )
    path = publish.resolve_output_path(
        None, str(tmp_path / "template.xml"), _TYPE
    )
    assert calls == [
        (
            (
                "Calling generate_xml without output_path writes next to "
                "the template and requires it to be under the current "
                "working directory; pass output_path explicitly instead.",
                DeprecationWarning,
            ),
            {"stacklevel": 3},
        )
    ]
    assert path == os.path.realpath(str(tmp_path / f"{_TYPE}.xml"))


def test_an_explicit_output_path_gets_its_directory_created(
    tmp_path: Path,
) -> None:
    """A destination in a new directory is returned with the directory made."""
    target = tmp_path / "new" / "out.xml"
    path = publish.resolve_output_path(str(target), "unused.xml", _TYPE)
    assert path == os.path.realpath(str(target))
    assert (tmp_path / "new").is_dir()


def test_a_failed_path_validation_is_reported_with_its_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The validator's own message is kept in the error."""
    monkeypatch.chdir(tmp_path)

    def refuse(path: str) -> str:
        """Refuse every path."""
        raise OSError("nope")

    monkeypatch.setattr(pain001.security, "validate_path", refuse)
    with pytest.warns(DeprecationWarning), pytest.raises(ValueError) as err:
        publish.resolve_output_path(None, str(tmp_path / "t.xml"), _TYPE)
    assert str(err.value) == "Path validation failed: nope"


def test_a_path_outside_the_working_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal names the path it would have written."""
    monkeypatch.chdir(tmp_path)
    outside = os.path.realpath(str(tmp_path.parent / "elsewhere.xml"))
    monkeypatch.setattr(pain001.security, "validate_path", lambda p: outside)
    with pytest.warns(DeprecationWarning), pytest.raises(ValueError) as err:
        publish.resolve_output_path(None, str(tmp_path / "t.xml"), _TYPE)
    assert (
        str(err.value) == f"Output path outside working directory: {outside}"
    )


def test_a_template_is_read_as_utf8_and_its_refusals_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The encoding is named; both refusals carry their exact text."""
    with pytest.raises(ValueError) as err:
        _render._load_trusted_template_source(str(tmp_path / "t.txt"))
    assert str(err.value) == "Template path must point to an .xml file"

    template = tmp_path / "t.xml"
    template.write_text("{% include 'x' %}", encoding="utf-8")
    with pytest.raises(ValueError) as err:
        _render._load_trusted_template_source(str(template))
    assert str(err.value) == (
        "Template contains disabled Jinja filesystem directives"
    )

    template.write_text("<Document/>", encoding="utf-8")
    seen: list[dict[str, Any]] = []

    def spy(path: str, **kwargs: Any) -> Any:
        """Record the keyword arguments, then open as usual."""
        seen.append(kwargs)
        return io.StringIO(Path(path).read_text(**kwargs))

    monkeypatch.setattr(_render, "open", spy, raising=False)
    assert _render._load_trusted_template_source(str(template)) == (
        "<Document/>"
    )
    assert seen == [{"encoding": "utf-8"}]


def test_v03_requires_a_currency_on_every_row() -> None:
    """A row without a currency is named in the message-typed refusal."""
    rows = _rows()
    for key in ("payment_currency", "currency"):
        rows[0].pop(key, None)
    with pytest.raises(PaymentValidationError) as err:
        message_registry._prepare_xml_data_v03(rows)
    assert str(err.value).startswith(
        "Missing required fields for pain.001.001.03: "
        "row 1: currency (or payment_currency)."
    )


def test_v03_keeps_only_the_date_of_a_date_time_execution_date() -> None:
    """``requested_execution_date`` is cut to its first ten characters."""
    rows = _rows()
    rows[0]["requested_execution_date"] = "2026-01-02T10:00:00"
    context = message_registry._prepare_xml_data_v03(rows)
    assert context["requested_execution_date"] == "2026-01-02"


def test_v03_refuses_a_context_with_fewer_transactions_than_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows and transactions are paired strictly, never truncated."""
    real = message_registry._context_v09

    def short(data: list[dict[str, Any]]) -> dict[str, Any]:
        """The real context, missing its last transaction."""
        context = real(data)
        context["transactions"] = context["transactions"][:-1]
        return context

    monkeypatch.setattr(message_registry, "_context_v09", short)
    with pytest.raises(ValueError, match="zip"):
        message_registry._prepare_xml_data_v03(_rows())


def test_the_shared_context_does_not_apply_the_v09_field_gate() -> None:
    """The .03 preparer gates its own fields; the shared context does not."""
    rows = _rows()
    for key in ("payment_currency", "currency"):
        rows[0].pop(key, None)
    context = message_registry._context_v09(rows)
    assert len(context["transactions"]) == len(rows)


def test_table_name_refusals_carry_their_exact_text() -> None:
    """Both refusals say what a table name must look like."""
    with pytest.raises(ConfigurationError) as err:
        sanitize_table_name("")
    assert str(err.value) == "Table name cannot be empty"
    with pytest.raises(ConfigurationError) as err:
        sanitize_table_name("1x")
    assert str(err.value) == (
        "Invalid table name '1x'. Table names must start with a letter "
        "and contain only alphanumeric characters and underscores."
    )


class _Lines(logging.Handler):
    """Keep every formatted message."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Keep the message."""
        self.lines.append(record.getMessage())


def test_an_event_line_is_utc_stamped_with_sorted_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The timestamp is UTC from ``gmtime``; the JSON keys are sorted."""
    monkeypatch.setattr(
        events,
        "time",
        SimpleNamespace(strftime=time.strftime, gmtime=lambda: time.gmtime(0)),
    )
    logger = logging.getLogger("pain001.tests.event_line")
    handler = _Lines()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        events.log_event(logger, logging.INFO, "probe", zeta=1, alpha=2)
    finally:
        logger.removeHandler(handler)
    [line] = handler.lines
    keys = json.loads(line, object_pairs_hook=lambda p: [k for k, _ in p])
    assert keys == sorted(keys)
    assert json.loads(line)[Fields.TIMESTAMP] == "1970-01-01T00:00:00Z"


def test_a_request_id_is_created_once_per_context() -> None:
    """A fresh context gets an id, and keeps returning that same id."""
    first, second = contextvars.Context().run(
        lambda: (get_request_id(), get_request_id())
    )
    assert isinstance(first, str)
    assert first
    assert first == second


def test_a_singleton_that_fails_to_initialise_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the constructor sets no instance, get_instance says so."""
    monkeypatch.setattr(Context, "instance", None)
    monkeypatch.setattr(Context, "__init__", lambda self: None)
    with pytest.raises(RuntimeError) as err:
        Context.get_instance()
    assert str(err.value) == "Failed to initialize Context singleton"


def _validator(tmp_path: Path, schema: dict[str, Any]) -> SchemaValidator:
    """A validator for ``schema``, stored as the .03 schema in tmp_path."""
    (tmp_path / f"{_TYPE}.schema.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )
    return SchemaValidator(_TYPE, schema_dir=tmp_path)


def test_coercion_tolerates_a_schema_without_properties(
    tmp_path: Path,
) -> None:
    """With no declared properties, values pass through unchanged."""
    validator = _validator(tmp_path, {"type": "object"})
    data = {"n": "5"}
    assert validator._coerce_types_for_validation(data) == data


def test_coercion_continues_past_a_non_string_value(tmp_path: Path) -> None:
    """A typed value is skipped, and later strings are still coerced."""
    validator = _validator(
        tmp_path,
        {"type": "object", "properties": {"n": {"type": "integer"}}},
    )
    coerced = validator._coerce_types_for_validation({"a": 1, "n": "5"})
    assert coerced == {"a": 1, "n": 5}


def test_coercion_turns_only_true_and_false_into_booleans(
    tmp_path: Path,
) -> None:
    """Booleans are read case-insensitively; other text is left alone."""
    validator = _validator(
        tmp_path,
        {
            "type": "object",
            "properties": {
                "flag": {"type": "boolean"},
                "off": {"type": "boolean"},
                "maybe": {"type": "boolean"},
                "name": {"type": "string"},
            },
        },
    )
    coerced = validator._coerce_types_for_validation(
        {"flag": " True ", "off": "FALSE", "maybe": "yes", "name": "true"}
    )
    assert coerced == {
        "flag": True,
        "off": False,
        "maybe": "yes",
        "name": "true",
    }


def test_coercion_continues_past_a_value_it_cannot_convert(
    tmp_path: Path,
) -> None:
    """An unconvertible string is kept, and later strings are coerced."""
    validator = _validator(
        tmp_path,
        {
            "type": "object",
            "properties": {
                "bad": {"type": "integer"},
                "n": {"type": "integer"},
            },
        },
    )
    coerced = validator._coerce_types_for_validation({"bad": "x", "n": "5"})
    assert coerced == {"bad": "x", "n": 5}


def test_a_nested_error_path_is_dotted(tmp_path: Path) -> None:
    """The error path joins each step with a dot."""
    validator = _validator(
        tmp_path,
        {
            "type": "object",
            "properties": {
                "a": {
                    "type": "object",
                    "properties": {"b": {"type": "integer"}},
                }
            },
        },
    )
    [error] = validator.validate_data({"a": {"b": "x"}})
    assert error.path == "$.a.b"


def test_an_error_without_a_validator_name_is_ruled_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A best-match error lacking its validator keyword says ``unknown``."""
    validator = _validator(tmp_path, {"type": "object"})
    bare = SimpleNamespace(
        message="m", absolute_path=[], instance=1, validator=None
    )
    monkeypatch.setattr(
        jsonschema.exceptions, "best_match", lambda errors: bare
    )
    [error] = validator.validate_data({})
    assert (error.rule, error.path) == ("unknown", "$")
