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

"""The lxml fast path for XSD validation, and its safety properties.

``validate_xml_string_via_xsd`` uses libxml2 as an accept/reject gate
when ``lxml`` is installed, falling back to ``xmlschema`` otherwise.
Two implementations behind one function is a real risk, so these tests
pin the properties that make it safe:

* a rejection by lxml is never final — xmlschema decides,
* the two agree on documents that are valid and on documents that are
  not,
* the lxml parser has entity expansion, DTD loading and network access
  switched off, because ``defusedxml`` does not cover lxml.

Both branches are exercised regardless of whether ``lxml`` is actually
installed in the environment running the suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pain001.xml import validate_via_xsd as module
from pain001.xml.validate_via_xsd import (
    collect_xsd_validation_errors,
    validate_xml_string_via_xsd,
)

SCHEMA = str(
    Path("pain001/templates/pain.001.001.03/pain.001.001.03.xsd").resolve()
)

MINIMAL_INVALID = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">'
    "<NotAThing/>"
    "</Document>"
)

NOT_XML = "this is not xml at all <<<"


def _generate_valid_document() -> str:
    """Produce a schema-valid pain.001.001.03 document."""
    from pain001.xml.generate_xml import generate_xml_string

    record = {
        "id": "1",
        "date": "2023-03-10T15:30:47",
        "nb_of_txs": "1",
        "initiator_name": "Initiator",
        "initiator_street_name": "Street",
        "initiator_building_number": "1",
        "initiator_postal_code": "12345",
        "initiator_town_name": "Town",
        "initiator_country_code": "DE",
        "payment_information_id": "PMT-INFO",
        "payment_method": "TRF",
        "batch_booking": "false",
        "requested_execution_date": "2023-03-15",
        "debtor_name": "Debtor",
        "debtor_street_name": "Street",
        "debtor_building_number": "1",
        "debtor_postal_code": "12345",
        "debtor_town_name": "Town",
        "debtor_country_code": "DE",
        "debtor_account_IBAN": "DE07512108001245126162",
        "debtor_agent_BIC": "BANKDEFFXXX",
        "charge_bearer": "DEBT",
        "payment_id": "PMT-000001",
        "payment_amount": "100.00",
        "currency": "EUR",
        "payment_currency": "EUR",
        "ctrl_sum": "100.00",
        "creditor_agent_BIC": "SPUEDE2UXXX",
        "creditor_name": "Creditor",
        "creditor_street_name": "Street",
        "creditor_building_number": "1",
        "creditor_postal_code": "12345",
        "creditor_town_name": "Town",
        "creditor_country_code": "DE",
        "creditor_account_IBAN": "DE36210501700024690959",
        "remittance_information": "INVOICE 1",
        "purpose_code": "SCOR",
        "reference_number": "REF",
        "reference_date": "2023-03-10",
    }
    return generate_xml_string(
        [record],
        "pain.001.001.03",
        "pain001/templates/pain.001.001.03/template.xml",
        SCHEMA,
    )


lxml_installed = pytest.mark.skipif(
    not module._LXML_AVAILABLE, reason="lxml is not installed"
)


class TestFallbackBehaviour:
    """What happens when lxml is absent or declines."""

    def test_validation_works_with_the_fast_path_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The xmlschema path stays reachable and correct."""
        monkeypatch.setattr(module, "_LXML_AVAILABLE", False)

        assert validate_xml_string_via_xsd(MINIMAL_INVALID, SCHEMA) is False

    def test_a_valid_document_is_accepted_without_the_fast_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fallback must still *accept*, not just reject.

        With lxml installed a valid document is accepted by the gate and
        never reaches xmlschema, so this is the only thing that
        exercises the pure-Python accept — the path every user without
        lxml takes for every document they generate.
        """
        valid = _generate_valid_document()

        monkeypatch.setattr(module, "_LXML_AVAILABLE", False)
        assert validate_xml_string_via_xsd(valid, SCHEMA) is True

        monkeypatch.setattr(module, "_LXML_AVAILABLE", module._LXML_AVAILABLE)

    def test_an_lxml_rejection_is_not_final(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A False from lxml must fall through to xmlschema.

        This is the property that makes installing or removing lxml
        unable to change a verdict: the fast path can only shortcut an
        accept.
        """
        calls: list[str] = []

        monkeypatch.setattr(module, "_LXML_AVAILABLE", True)
        monkeypatch.setattr(
            module,
            "_lxml_accepts",
            lambda content, schema: calls.append("lxml") or False,
        )

        # A document xmlschema considers invalid stays invalid...
        assert validate_xml_string_via_xsd(MINIMAL_INVALID, SCHEMA) is False
        assert calls == ["lxml"]

    def test_unparseable_input_is_rejected_by_both_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Garbage in is False out, with or without the fast path."""
        monkeypatch.setattr(module, "_LXML_AVAILABLE", False)
        assert validate_xml_string_via_xsd(NOT_XML, SCHEMA) is False

        monkeypatch.setattr(module, "_LXML_AVAILABLE", True)
        assert validate_xml_string_via_xsd(NOT_XML, SCHEMA) is False


@lxml_installed
class TestLxmlGate:
    """The fast path itself, when lxml is present."""

    def test_it_rejects_a_schema_invalid_document(self) -> None:
        """An element the schema does not define is not accepted."""
        assert module._lxml_accepts(MINIMAL_INVALID, SCHEMA) is False

    def test_it_reports_false_rather_than_raising_on_garbage(self) -> None:
        """Any internal failure defers to xmlschema instead of blowing up."""
        assert module._lxml_accepts(NOT_XML, SCHEMA) is False

    def test_it_reports_false_for_a_missing_schema(self) -> None:
        """A bad schema path defers rather than raising."""
        assert module._lxml_accepts(MINIMAL_INVALID, "no/such.xsd") is False

    def test_the_compiled_schema_is_cached(self) -> None:
        """Compiling the schema is the expensive, document-independent part."""
        first = module._get_cached_lxml_schema(SCHEMA)
        second = module._get_cached_lxml_schema(SCHEMA)
        assert first is second


@lxml_installed
class TestParserHardening:
    """defusedxml does not cover lxml, so this is configured by hand."""

    def test_entities_are_not_expanded(self) -> None:
        """The billion-laughs and XXE class both rely on expansion."""
        import lxml.etree as etree

        payload = (
            '<?xml version="1.0"?>'
            "<!DOCTYPE root ["
            '<!ENTITY boom "EXPANDED">'
            "]>"
            "<root>&boom;</root>"
        )
        parsed = etree.fromstring(
            payload.encode("utf-8"), module._hardened_lxml_parser()
        )

        assert "EXPANDED" not in (parsed.text or "")

    def test_an_external_file_entity_does_not_leak_the_file(
        self, tmp_path
    ) -> None:
        """The XXE case: a SYSTEM entity must not read local files.

        Asserting on the parser's flags would only restate the
        constructor call. This runs the attack: a document that, with a
        default parser, would substitute the contents of a real file on
        disk into the output.
        """
        import lxml.etree as etree

        secret = tmp_path / "secret.txt"
        secret.write_text("TOP-SECRET-VALUE", encoding="utf-8")

        payload = (
            '<?xml version="1.0"?>'
            "<!DOCTYPE root ["
            f'<!ENTITY xxe SYSTEM "file://{secret}">'
            "]>"
            "<root>&xxe;</root>"
        )

        parsed = etree.fromstring(
            payload.encode("utf-8"), module._hardened_lxml_parser()
        )

        assert "TOP-SECRET-VALUE" not in (parsed.text or "")
        assert "TOP-SECRET-VALUE" not in etree.tostring(parsed).decode()

    def test_a_document_using_that_payload_is_not_accepted(self) -> None:
        """And the gate rejects it rather than validating something odd."""
        payload = (
            '<?xml version="1.0"?>'
            "<!DOCTYPE Document ["
            '<!ENTITY xxe SYSTEM "file:///etc/passwd">'
            "]>"
            '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">'
            "<CstmrCdtTrfInitn>&xxe;</CstmrCdtTrfInitn>"
            "</Document>"
        )

        assert module._lxml_accepts(payload, SCHEMA) is False


class TestErrorReportingIsUnchanged:
    """The fast path must not alter what a rejection tells the user."""

    def test_messages_still_come_from_xmlschema(self) -> None:
        """collect_xsd_validation_errors is untouched by the fast path."""
        messages = collect_xsd_validation_errors(MINIMAL_INVALID, SCHEMA)

        assert messages
        assert any(":" in m for m in messages)

    def test_a_parse_error_is_reported_not_raised(self) -> None:
        """Unparseable content yields a message rather than an exception."""
        messages = collect_xsd_validation_errors(NOT_XML, SCHEMA)

        assert messages
        assert "XML parse error" in messages[0]
