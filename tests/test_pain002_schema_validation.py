"""Bundled-schema validation for pain.002 bank responses.

The parser is namespace-agnostic by design — a bank may answer in any
pain.002 version — so ``validate=True`` resolves the schema from the
document itself. The important property is the negative one: when no
bundled schema covers the version, it must refuse rather than parse
unvalidated, because a silent skip reports a validation that never
happened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.exceptions import DataSourceError, SchemaValidationError
from pain001.pain002 import parse_pain002_report
from pain001.pain002.parser import (
    bundled_schema_versions,
    schema_for_namespace,
)

FIXTURES = Path(__file__).resolve().parent.parent / "pain001" / "test_fixtures"
V15 = FIXTURES / "pain002_v15_sample.xml"
V03 = FIXTURES / "pain002_sample.xml"
V14_UNBUNDLED = FIXTURES / "pain002_v14_unbundled.xml"


def test_bundled_versions_are_discoverable() -> None:
    versions = bundled_schema_versions()
    assert versions, "no pain.002 schemas bundled"
    assert all(v.startswith("pain.002.001.") for v in versions)


def test_namespace_resolves_to_a_bundled_schema() -> None:
    ns = "{urn:iso:std:iso:20022:tech:xsd:pain.002.001.15}"
    schema = schema_for_namespace(ns)
    assert schema is not None and schema.is_file()


def test_unbundled_namespace_resolves_to_nothing() -> None:
    ns = "{urn:iso:std:iso:20022:tech:xsd:pain.002.001.99}"
    assert schema_for_namespace(ns) is None


def test_validate_true_accepts_a_valid_document() -> None:
    report = parse_pain002_report(str(V15), validate=True)
    assert report["message_id"] == "STAT-V15-001"
    assert report["payment_statuses"][0]["transaction_status"] == "RJCT"


def test_validate_true_refuses_an_unbundled_version() -> None:
    """pain.002.001.14 is a real ISO version this package does not ship.

    The refusal is the point: a bank may answer in any version, and
    parsing unvalidated while reporting success would be worse than
    saying plainly that the check could not be performed.
    """
    with pytest.raises(SchemaValidationError) as exc:
        parse_pain002_report(str(V14_UNBUNDLED), validate=True)
    message = str(exc.value)
    assert "No bundled schema" in message
    # the error must tell the caller what to do next
    assert "xsd_file_path" in message
    assert bundled_schema_versions()[0] in message


def test_unbundled_version_still_parses_without_validation() -> None:
    """Refusing to validate must not mean refusing to parse."""
    report = parse_pain002_report(str(V14_UNBUNDLED))
    assert report["message_id"] == "STAT-V14-001"


def test_sepa_v03_responses_can_now_be_validated() -> None:
    """pain.002.001.03 is what SEPA banks commonly reply with."""
    report = parse_pain002_report(str(V03), validate=True)
    assert report["payment_statuses"][0]["status_reason"] == "AC04"


def test_validate_true_rejects_a_corrupted_document(tmp_path: Path) -> None:
    """Proof the schema is actually consulted, not merely located."""
    broken = tmp_path / "broken.xml"
    broken.write_text(
        V15.read_text(encoding="utf-8").replace(
            "<MsgId>STAT-V15-001</MsgId>", "<NotAnElement>x</NotAnElement>"
        ),
        encoding="utf-8",
    )
    with pytest.raises(SchemaValidationError):
        parse_pain002_report(str(broken), validate=True)


def test_validate_true_reports_malformed_xml_clearly(tmp_path: Path) -> None:
    """Malformed input must fail as a data error, not a schema error."""
    bad = tmp_path / "malformed.xml"
    bad.write_text("<Document><unclosed>", encoding="utf-8")
    with pytest.raises(DataSourceError) as exc:
        parse_pain002_report(str(bad), validate=True)
    assert "Invalid pain.002 XML" in str(exc.value)
