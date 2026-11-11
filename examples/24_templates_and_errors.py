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

"""Template registry, typed errors, scheme results and metric events.

Covers the public pieces an integrator reaches for once generation
works and the question becomes "what can go wrong, and how do I tell":

* ``DEFAULT_TEMPLATE_REGISTRY`` / ``TemplateRegistry`` - discover the
  bundled message types, or index a directory of your own bundles
* ``validate_registry`` - the drift guardrail that refuses a bundle
  whose template or schema names a different message type
* ``DataSourceError`` / ``PaymentValidationError`` - the typed errors
  for "cannot read the input" and "the input is wrong"
* ``RowIssue`` / ``IssueCode`` - one record per bad row and column on
  ``PaymentValidationError.errors``, with a stable code and no value
* ``SchemeValidationResult`` / ``SchemeViolation`` - the structured
  result ``validate_scheme`` returns, with ``as_dict()`` for JSON
* ``MetricEvent`` - what a ``register_metrics_callback`` hook receives

All inputs are synthetic; temporary files live outside the repository.

Run from the repository root::

    python examples/24_templates_and_errors.py
"""

import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from pain001 import (
    DEFAULT_TEMPLATE_REGISTRY,
    DataSourceError,
    IssueCode,
    MetricEvent,
    PaymentValidationError,
    RowIssue,
    SchemeValidationResult,
    SchemeViolation,
    TemplateRegistry,
    clear_metrics_callbacks,
    generate_xml_string,
    normalize_payment_records,
    process_files,
    register_metrics_callback,
    validate_registry,
    validate_scheme,
)
from pain001.csv.load_csv_data import load_csv_data
from pain001.data import load_payment_data
from pain001.templates.guardrails import SchemaGuardrailError

MESSAGE_TYPE = "pain.001.001.03"
DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"


def expect(
    error: type[Exception], call: Callable[..., object], *args: object
) -> Exception:
    """Run ``call`` and return the ``error`` it must raise.

    Args:
        error: The exception type the call is expected to raise.
        call: The callable under test.
        *args: Positional arguments for ``call``.

    Returns:
        The caught exception, for assertions on its message and fields.
    """
    try:
        call(*args)
    except error as exc:
        return exc
    raise AssertionError(f"{call.__name__} did not raise {error.__name__}")


def _default_registry() -> None:
    """Query the bundled templates and run the drift guardrail."""
    versions = DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
    assert MESSAGE_TYPE in versions
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(MESSAGE_TYPE)
    assert meta.message_category == "CustomerCreditTransferInitiation"
    assert meta.template_path.is_file() and meta.xsd_path.is_file()
    debits = DEFAULT_TEMPLATE_REGISTRY.search_by_category(
        "customerdirectdebitinitiation"
    )
    assert debits and all(
        m.message_type.startswith("pain.008") for m in debits
    )
    assert validate_registry() == versions
    print(f"Default registry: {len(versions)} bundles, all validated")
    print(f"  {MESSAGE_TYPE}: {meta.message_category}, iso {meta.iso_version}")
    print(f"  direct debit bundles: {[m.message_type for m in debits]}")
    exc = expect(
        KeyError, DEFAULT_TEMPLATE_REGISTRY.get_template, "pain.001.001.99"
    )
    assert "Unsupported template 'pain.001.001.99'" in str(exc)
    print("  unknown type -> KeyError listing the known values")


def _custom_registry(root: Path) -> None:
    """Index a private bundle directory, then catch a drifted bundle."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(MESSAGE_TYPE)
    bundle = root / MESSAGE_TYPE
    shutil.copytree(meta.template_path.parent, bundle)
    registry = TemplateRegistry(root)
    assert registry.list_supported_versions() == [MESSAGE_TYPE]
    assert validate_registry(registry) == [MESSAGE_TYPE]
    print(f"Custom registry: {registry.list_supported_versions()} validated")

    # Point the bundle's metadata at the schema of another version.
    other = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.09")
    shutil.copy(other.xsd_path, bundle)
    metadata = bundle / "metadata.yaml"
    text = metadata.read_text(encoding="utf-8")
    metadata.write_text(
        text.replace(meta.xsd_path.name, other.xsd_path.name),
        encoding="utf-8",
    )
    exc = expect(
        SchemaGuardrailError, validate_registry, TemplateRegistry(root)
    )
    assert "Message type drift" in str(exc)
    print("  drifted bundle -> SchemaGuardrailError (message type drift)")


def _typed_errors(workdir: Path) -> None:
    """Trigger and catch each typed error through the public API."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(MESSAGE_TYPE)
    unsupported = workdir / "payments.txt"
    unsupported.write_text("not a payment file\n", encoding="utf-8")
    exc = expect(
        DataSourceError,
        process_files,
        MESSAGE_TYPE,
        str(meta.template_path),
        str(meta.xsd_path),
        str(unsupported),
    )
    assert "Unsupported file type" in str(exc)
    print("Unsupported .txt input -> DataSourceError")

    rows = load_csv_data(str(DATA_FILE))
    rows[0]["payment_amount"] = "12.345"
    error = expect(PaymentValidationError, normalize_payment_records, rows)
    assert isinstance(error, PaymentValidationError)
    assert error.field == "payment_amount"
    assert "more than two decimal places" in str(error)
    print(f"Over-precise amount -> PaymentValidationError ({error.field})")

    rows = load_csv_data(str(DATA_FILE))
    rows[1]["payment_amount"] = "twelve"
    error = expect(PaymentValidationError, load_payment_data, rows)
    assert isinstance(error, PaymentValidationError)
    issue = error.errors[0]
    assert isinstance(issue, RowIssue)
    assert (issue.line, issue.column) == (2, "payment_amount")
    assert issue.code == IssueCode.NOT_DECIMAL
    assert "twelve" not in str(error)
    print(f"Bad amount -> {issue}")


def _scheme_result() -> None:
    """Inspect the structured result of a failed scheme check."""
    row = load_csv_data(str(DATA_FILE))[0] | {"payment_currency": "USD"}
    result = validate_scheme([row], profile="sepa-sct")
    assert isinstance(result, SchemeValidationResult)
    assert result.profile == "sepa-sct"
    assert not result.is_valid and not result
    violation = result.violations[0]
    assert isinstance(violation, SchemeViolation)
    assert violation.index == 0 and violation.severity == "error"
    assert violation.remediation, "every bundled rule ships a fix hint"
    payload = violation.as_dict()
    assert set(payload) == {
        "rule",
        "message",
        "index",
        "field",
        "severity",
        "remediation",
    }
    json.dumps(payload)  # JSON-serialisable as documented
    print(f"Scheme result ({result.profile}): {len(result.violations)} issue")
    print(f"  as_dict: rule={payload['rule']} field={payload['field']}")
    print(f"  fix: {violation.remediation}")


def _metric_events() -> None:
    """Receive MetricEvent objects from an in-memory generation."""
    meta = DEFAULT_TEMPLATE_REGISTRY.get_template(MESSAGE_TYPE)
    rows = load_csv_data(str(DATA_FILE))
    events: list[MetricEvent] = []
    register_metrics_callback(events.append)
    try:
        xml = generate_xml_string(
            rows, MESSAGE_TYPE, str(meta.template_path), str(meta.xsd_path)
        )
    finally:
        clear_metrics_callbacks()
    assert xml.startswith("<?xml")
    prepared = next(e for e in events if e.name == "xml_prepared")
    assert isinstance(prepared, MetricEvent)
    assert prepared.timestamp > 0
    assert prepared.attributes["message_type"] == MESSAGE_TYPE
    assert prepared.attributes["record_count"] == len(rows)
    assert isinstance(prepared.trace_context, dict)
    print(f"Metric events: {[e.name for e in events]}")
    print(f"  xml_prepared attributes: {prepared.attributes}")


def main() -> None:
    """Run each section against synthetic inputs."""
    _default_registry()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "bundles").mkdir()
        _custom_registry(root / "bundles")
        _typed_errors(root)
    _scheme_result()
    _metric_events()


if __name__ == "__main__":
    main()
