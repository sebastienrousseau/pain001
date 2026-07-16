# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""LLM-ergonomic generate-path regression tests (v0.0.54).

Covers the failure catalogue from a real agent transcript driving the
iso20022-mcp gateway: field aliases (``amount``/``currency``), bare-date
coercion for ``CreDtTm``, computed ``nb_of_txs``/``ctrl_sum``, boolean
serialization, the silent ``Ccy=""`` bug, single-shot missing-field
errors, the unconditional ``SplmtryData`` block, and detailed XSD error
reporting.
"""

from pathlib import Path

import pytest

from pain001 import (
    canonicalize_payment_record,
    generate_xml_string,
    normalize_payment_records,
)
from pain001.constants import TEMPLATES_DIR
from pain001.exceptions import PaymentValidationError
from pain001.xml import generate_xml as generate_xml_module
from pain001.xml.message_registry import prepare_xml_data
from pain001.xml.validate_via_xsd import (
    collect_xsd_validation_errors,
    validate_xml_string_via_xsd,
)

V09 = "pain.001.001.09"
V09_DIR = Path(TEMPLATES_DIR) / V09
V09_TEMPLATE = str(V09_DIR / "template.xml")
V09_XSD = str(V09_DIR / f"{V09}.xsd")


def natural_record(**overrides):
    """A record shaped the way an LLM naturally produces it.

    Bare execution-date, JSON boolean, ``amount``/``currency`` key names,
    and no ``nb_of_txs``/``ctrl_sum`` header fields.
    """
    record = {
        "id": "MSG-20260716-001",
        "date": "2026-07-18",
        "initiator_name": "Sebastien Rousseau",
        "payment_id": "PMT-001",
        "payment_method": "TRF",
        "batch_booking": False,
        "requested_execution_date": "2026-07-18",
        "debtor_name": "Sebastien Rousseau",
        "debtor_account_IBAN": "DE89370400440532013000",
        "debtor_agent_BIC": "DEUTDEFFXXX",
        "charge_bearer": "SLEV",
        "creditor_name": "Acme GmbH",
        "creditor_agent_BIC": "COBADEFFXXX",
        "creditor_account_IBAN": "DE75512108001245126199",
        "amount": 4200,
        "currency": "EUR",
        "remittance_information": "Invoice 2026-078",
    }
    record.update(overrides)
    return record


def generate_v09(records):
    """Generate a pain.001.001.09 document from the given records."""
    return generate_xml_string(records, V09, V09_TEMPLATE, V09_XSD)


class TestNaturalCallHappyPath:
    """The user's natural first-try call must succeed in one shot."""

    def test_natural_record_generates_valid_xml_first_try(self):
        xml = generate_v09([natural_record()])
        assert validate_xml_string_via_xsd(xml, V09_XSD)
        assert 'Ccy="EUR"' in xml
        assert ">4200.00<" in xml
        assert "<CreDtTm>2026-07-18T00:00:00</CreDtTm>" in xml
        assert "<Nm>Acme GmbH</Nm>" in xml

    def test_supplementary_data_block_omitted_by_default(self):
        xml = generate_v09([natural_record()])
        assert "SplmtryData" not in xml

    def test_supplementary_data_emitted_when_provided(self):
        xml = generate_v09([natural_record(supplementary_data="ACME-REF-42")])
        assert "<SplmtryData>" in xml
        assert "ACME-REF-42" in xml
        assert validate_xml_string_via_xsd(xml, V09_XSD)


class TestFieldAliases:
    """amount/currency and lower-case identifier spellings are accepted."""

    def test_amount_aliases_payment_amount(self):
        rows = normalize_payment_records([natural_record()])
        assert rows[0]["payment_amount"] == "4200.00"

    def test_currency_mirrors_payment_currency_both_ways(self):
        rows = normalize_payment_records([natural_record()])
        assert rows[0]["payment_currency"] == "EUR"
        rows = normalize_payment_records(
            [natural_record(currency=None, payment_currency="GBP")]
        )
        assert rows[0]["currency"] == "GBP"

    def test_alias_never_overrides_explicit_canonical_value(self):
        rows = normalize_payment_records(
            [natural_record(payment_amount="12.50", amount=99)]
        )
        assert rows[0]["payment_amount"] == "12.50"

    def test_lowercase_identifier_keys_are_canonicalized(self):
        record = natural_record()
        record["creditor_agent_bic"] = record.pop("creditor_agent_BIC")
        record["creditor_account_iban"] = record.pop("creditor_account_IBAN")
        record["debtor_account_iban"] = record.pop("debtor_account_IBAN")
        record["debtor_agent_bic"] = record.pop("debtor_agent_BIC")
        xml = generate_v09([record])
        assert "COBADEFFXXX" in xml

    def test_instructed_amount_alias(self):
        record = natural_record()
        record["instructed_amount"] = record.pop("amount")
        rows = normalize_payment_records([record])
        assert rows[0]["payment_amount"] == "4200.00"

    def test_execution_date_alias(self):
        record = natural_record()
        record["execution_date"] = record.pop("requested_execution_date")
        rows = normalize_payment_records([record])
        assert rows[0]["requested_execution_date"] == "2026-07-18"

    def test_canonicalize_maps_keys_without_reformatting_values(self):
        row = canonicalize_payment_record(
            {"amount": 4200, "currency": "EUR", "batch_booking": False}
        )
        assert row["payment_amount"] == 4200
        assert row["payment_currency"] == "EUR"
        assert row["batch_booking"] is False

    def test_input_rows_are_not_mutated(self):
        record = natural_record()
        normalize_payment_records([record])
        assert record["amount"] == 4200
        assert record["batch_booking"] is False


class TestTemporalCoercion:
    """Dates are coerced to the XSD lexical form each element requires."""

    def test_bare_date_becomes_midnight_datetime(self):
        rows = normalize_payment_records([natural_record()])
        assert rows[0]["date"] == "2026-07-18T00:00:00"

    def test_space_separated_datetime_normalized(self):
        rows = normalize_payment_records(
            [natural_record(date="2026-07-18 09:30:00")]
        )
        assert rows[0]["date"] == "2026-07-18T09:30:00"

    def test_full_datetime_passes_through(self):
        rows = normalize_payment_records(
            [natural_record(date="2026-07-18T09:30:00")]
        )
        assert rows[0]["date"] == "2026-07-18T09:30:00"

    def test_execution_datetime_truncated_to_date(self):
        rows = normalize_payment_records(
            [natural_record(requested_execution_date="2026-07-18T09:30:00")]
        )
        assert rows[0]["requested_execution_date"] == "2026-07-18"

    def test_non_string_temporal_values_left_alone(self):
        rows = normalize_payment_records(
            [natural_record(date=20260718, requested_execution_date=None)]
        )
        assert rows[0]["date"] == 20260718
        assert rows[0]["requested_execution_date"] is None


class TestBooleanCoercion:
    """Python/JSON booleans and their string forms render as XSD booleans."""

    def test_python_bool_renders_lowercase(self):
        rows = normalize_payment_records([natural_record(batch_booking=True)])
        assert rows[0]["batch_booking"] == "true"

    def test_titlecase_string_bool_normalized(self):
        rows = normalize_payment_records(
            [natural_record(batch_booking="False")]
        )
        assert rows[0]["batch_booking"] == "false"

    def test_other_strings_left_untouched(self):
        rows = normalize_payment_records(
            [natural_record(batch_booking="maybe")]
        )
        assert rows[0]["batch_booking"] == "maybe"


class TestComputedTotals:
    """nb_of_txs and ctrl_sum are computed, never trusted from input."""

    def test_totals_computed_from_records(self):
        rows = normalize_payment_records(
            [
                natural_record(),
                natural_record(payment_id="PMT-002", amount="99.50"),
            ]
        )
        assert all(row["nb_of_txs"] == 2 for row in rows)
        assert all(row["ctrl_sum"] == 4299.50 for row in rows)

    def test_caller_supplied_totals_are_overridden(self):
        rows = normalize_payment_records(
            [natural_record(nb_of_txs=17, ctrl_sum=1.23)]
        )
        assert rows[0]["nb_of_txs"] == 1
        assert rows[0]["ctrl_sum"] == 4200.0

    def test_generate_without_nb_of_txs_succeeds(self):
        record = natural_record()
        assert "nb_of_txs" not in record
        xml = generate_v09([record])
        assert "<NbOfTxs>1</NbOfTxs>" in xml


class TestSingleShotErrors:
    """Every missing/invalid field is reported at once, actionably."""

    def test_missing_fields_listed_together(self):
        with pytest.raises(PaymentValidationError) as excinfo:
            generate_v09([{"amount": 1, "currency": "EUR", "payment_id": "X"}])
        message = str(excinfo.value)
        for field in (
            "id",
            "date",
            "initiator_name",
            "debtor_account_IBAN",
            "creditor_agent_BIC",
            "creditor_account_IBAN",
        ):
            assert field in message
        assert "aliases are accepted" in message

    def test_missing_currency_is_named_not_silent(self):
        record = natural_record()
        del record["currency"]
        with pytest.raises(PaymentValidationError) as excinfo:
            generate_v09([record])
        assert "currency (or payment_currency)" in str(excinfo.value)
        assert 'Ccy=""' not in str(excinfo.value)

    def test_per_row_errors_carry_row_numbers(self):
        good = natural_record()
        bad = natural_record(payment_id="PMT-002")
        del bad["creditor_name"]
        with pytest.raises(PaymentValidationError) as excinfo:
            generate_v09([good, bad])
        assert "row 2: creditor_name" in str(excinfo.value)

    def test_v03_missing_fields_listed_together(self):
        with pytest.raises(PaymentValidationError) as excinfo:
            prepare_xml_data(
                [{"payment_amount": "1.00", "currency": "EUR"}],
                "pain.001.001.03",
            )
        message = str(excinfo.value)
        assert "pain.001.001.03" in message
        assert "initiator_street_name" in message
        assert "purpose_code" in message

    def test_v03_defaults_for_method_booking_and_charge_bearer(self):
        row = {
            "id": "1",
            "date": "2026-07-18T00:00:00",
            "initiator_name": "A",
            "initiator_street_name": "S",
            "initiator_building_number": "1",
            "initiator_postal_code": "P",
            "initiator_town_name": "T",
            "initiator_country_code": "DE",
            "payment_id": "P1",
            "requested_execution_date": "2026-07-18",
            "debtor_name": "D",
            "debtor_street_name": "S",
            "debtor_building_number": "2",
            "debtor_postal_code": "P",
            "debtor_town_name": "T",
            "debtor_country_code": "DE",
            "debtor_account_IBAN": "DE89370400440532013000",
            "debtor_agent_BIC": "DEUTDEFFXXX",
            "creditor_agent_BIC": "COBADEFFXXX",
            "creditor_name": "C",
            "creditor_street_name": "S",
            "creditor_building_number": "3",
            "creditor_postal_code": "P",
            "creditor_town_name": "T",
            "creditor_country_code": "DE",
            "creditor_account_IBAN": "DE75512108001245126199",
            "purpose_code": "OTHR",
            "reference_number": "R1",
            "reference_date": "2026-07-18",
            "payment_amount": "1.00",
            "currency": "EUR",
        }
        prepared = prepare_xml_data([row], "pain.001.001.03")
        assert prepared["payment_method"] == "TRF"
        assert prepared["batch_booking"] == "false"
        assert prepared["charge_bearer"] == "SLEV"
        assert prepared["transactions"][0]["payment_currency"] == "EUR"

    def test_v05_currency_alias(self):
        prepared = prepare_xml_data(
            [{"payment_amount": "1.00", "currency": "CHF"}],
            "pain.001.001.05",
        )
        assert prepared["transactions"][0]["payment_currency"] == "CHF"


class TestXsdErrorDetail:
    """XSD failures report every violation with element paths."""

    def test_invalid_enum_reports_path_and_reason(self):
        record = natural_record(charge_bearer="INVALID")
        with pytest.raises(RuntimeError) as excinfo:
            generate_v09([record])
        message = str(excinfo.value)
        assert "ChrgBr" in message
        assert "failed validation" in message

    def test_unknown_reason_fallback(self, monkeypatch):
        monkeypatch.setattr(
            generate_xml_module,
            "validate_xml_string_via_xsd",
            lambda *_: False,
        )
        monkeypatch.setattr(
            generate_xml_module,
            "collect_xsd_validation_errors",
            lambda *_: [],
        )
        with pytest.raises(RuntimeError) as excinfo:
            generate_v09([natural_record()])
        assert "unknown reason" in str(excinfo.value)

    def test_collect_errors_valid_document_returns_empty(self):
        xml = generate_v09([natural_record()])
        assert collect_xsd_validation_errors(xml, V09_XSD) == []

    def test_collect_errors_lists_violations(self):
        xml = generate_v09([natural_record()]).replace(
            "<ChrgBr>SLEV</ChrgBr>", "<ChrgBr>BAD1</ChrgBr>"
        )
        errors = collect_xsd_validation_errors(xml, V09_XSD)
        assert errors
        assert any("ChrgBr" in message for message in errors)

    def test_collect_errors_respects_cap(self):
        xml = generate_v09(
            [
                natural_record(),
                natural_record(payment_id="PMT-002"),
            ]
        ).replace("SLEV", "BAD1")
        errors = collect_xsd_validation_errors(xml, V09_XSD, max_errors=1)
        assert len(errors) == 1

    def test_collect_errors_parse_failure(self):
        errors = collect_xsd_validation_errors("<not-xml", V09_XSD)
        assert len(errors) == 1
        assert "XML parse error" in errors[0]

    def test_collect_errors_schema_load_failure(self, tmp_path):
        xml = generate_v09([natural_record()])
        missing_xsd = tmp_path / "missing.xsd"
        errors = collect_xsd_validation_errors(xml, str(missing_xsd))
        assert len(errors) == 1
        assert "XSD schema load error" in errors[0]
