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

"""Tests for ISO Schematron business rules engine."""

import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from pain001.cli.cli import cli
from pain001.core.core import process_files, process_files_streaming
from pain001.exceptions import XMLGenerationError
from pain001.schematron import (
    PRESET_RULEBOOKS,
    SchematronAssertion,
    SchematronValidationResult,
    SchematronValidator,
    SchematronViolation,
    parse_schematron,
    remediation_for,
    resolve_rulebook_path,
    validate_schematron,
)
from pain001.schematron.evaluator import (
    XPathEvaluator,
    _local_tag,
    _match_tag,
    _tokenize,
    evaluate_assertion,
    find_context_elements,
    resolve_xpath_value,
)

SAMPLE_SEPA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>MSG-2026-001</MsgId>
      <CreDtTm>2026-09-27T10:00:00Z</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <InitgPty>
        <Nm>Acme Corp</Nm>
      </InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>PMT-001</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <PmtTpInf>
        <SvcLvl>
          <Cd>SEPA</Cd>
        </SvcLvl>
      </PmtTpInf>
      <Dbtr>
        <Nm>Acme Corp</Nm>
      </Dbtr>
      <DbtrAcct>
        <Id>
          <IBAN>FR7630006000011234567890189</IBAN>
        </Id>
      </DbtrAcct>
      <ChrgBr>SLEV</ChrgBr>
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>E2E-12345</EndToEndId>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="EUR">250.75</InstdAmt>
        </Amt>
        <CdtrAgt>
          <FinInstnId>
            <BIC>BNPAFRPPXXX</BIC>
          </FinInstnId>
        </CdtrAgt>
        <Cdtr>
          <Nm>Supplier SA</Nm>
        </Cdtr>
        <CdtrAcct>
          <Id>
            <IBAN>FR7630004000031234567890143</IBAN>
          </Id>
        </CdtrAcct>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
"""

SAMPLE_FEDNOW_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>FEDNOW-MSG-01</MsgId>
      <CreDtTm>2026-09-27T10:00:00Z</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>FEDNOW-PMT-01</PmtInfId>
      <PmtTpInf>
        <ClrSysPrvdr>
          <Prtry>FDN</Prtry>
        </ClrSysPrvdr>
      </PmtTpInf>
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>FN-TX-001</EndToEndId>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="USD">50000.00</InstdAmt>
        </Amt>
        <ChrgBr>DEBT</ChrgBr>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
"""

SAMPLE_CBPR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>CBPR-MSG-01</MsgId>
      <CreDtTm>2026-09-27T10:00:00Z</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>CBPR-PMT-01</PmtInfId>
      <CdtTrfTxInf>
        <PmtId>
          <EndToEndId>XB-E2E-999</EndToEndId>
          <UETR>c56a4180-65aa-42ec-a945-5fd21dec0538</UETR>
        </PmtId>
        <Amt>
          <InstdAmt Ccy="GBP">12500.00</InstdAmt>
        </Amt>
        <CdtrAgt>
          <FinInstnId>
            <BICFI>MIDLGB22</BICFI>
          </FinInstnId>
        </CdtrAgt>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>
"""


class TestSchematronModels:
    """Test Schematron models and diagnostic representations."""

    def test_remediation_lookup(self) -> None:
        assert "EUR" in remediation_for("EPC-SCT-001")
        assert "FedNow" in remediation_for("FDN-TX-002")
        assert "Schematron" in remediation_for("UNKNOWN-RULE-XYZ")

    def test_violation_model(self) -> None:
        v = SchematronViolation(
            rule_id="EPC-SCT-001",
            message="Currency must be EUR",
            context="//pain:CdtTrfTxInf",
            test="pain:Amt/@Ccy = 'EUR'",
            line_number=42,
            severity="ERROR",
        )
        assert v.rule_id == "EPC-SCT-001"
        assert v.line_number == 42
        assert "EUR" in v.remediation
        d = v.to_dict()
        assert d["rule_id"] == "EPC-SCT-001"
        assert d["severity"] == "ERROR"
        assert d["line_number"] == 42

    def test_validation_result_model(self) -> None:
        res = SchematronValidationResult(
            is_valid=True,
            rulebook="sepa",
            violations=[],
            rules_evaluated=9,
            rules_passed=9,
            duration_ms=1.25,
        )
        assert res.error_count == 0
        assert res.warning_count == 0
        assert "PASSED" in res.format_report()

        # Add an error violation
        v_err = SchematronViolation(
            rule_id="EPC-SCT-001",
            message="Currency mismatch",
            context="//pain:CdtTrfTxInf",
            test="pain:Amt/@Ccy = 'EUR'",
            severity="ERROR",
        )
        v_warn = SchematronViolation(
            rule_id="WARN-001",
            message="Advisory check",
            context="//pain:PmtInf",
            test="true()",
            severity="WARNING",
            remediation="Check documentation.",
        )
        res_fail = SchematronValidationResult(
            is_valid=False,
            rulebook="sepa",
            violations=[v_err, v_warn],
            rules_evaluated=10,
            rules_passed=8,
            duration_ms=2.5,
        )
        assert res_fail.error_count == 1
        assert res_fail.warning_count == 1
        report = res_fail.format_report()
        assert "FAILED" in report
        assert "EPC-SCT-001" in report
        assert "WARN-001" in report

        d = res_fail.to_dict()
        assert d["is_valid"] is False
        assert len(d["violations"]) == 2


class TestSchematronParser:
    """Test parsing of Schematron XML documents."""

    def test_parse_presets(self) -> None:
        for preset in ("sepa", "fednow", "cbpr"):
            schema_path = resolve_rulebook_path(preset)
            assert schema_path.exists()
            schema = parse_schematron(schema_path)
            assert schema.title != ""
            assert schema.total_assertions > 0
            assert "pain" in schema.namespaces

    def test_parse_from_string_and_bytes(self) -> None:
        sch_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <schema xmlns="http://purl.oclc.org/dsdl/schematron">
          <title>Test Schema</title>
          <ns prefix="test" uri="urn:test:ns"/>
          <pattern id="P1">
            <title>Pattern One</title>
            <rule context="//test:Item">
              <assert test="@active = 'true'" id="RULE-01" role="error">
                Item must be active
              </assert>
              <report test="@expired = 'true'" id="RULE-02" role="warn">
                Item is expired
              </report>
            </rule>
          </pattern>
        </schema>
        """
        schema_str = parse_schematron(sch_xml)
        assert schema_str.title == "Test Schema"
        assert schema_str.namespaces["test"] == "urn:test:ns"
        assert len(schema_str.patterns) == 1
        p = schema_str.patterns[0]
        assert p.pattern_id == "P1"
        assert len(p.rules) == 1
        r = p.rules[0]
        assert r.context == "//test:Item"
        assert len(r.assertions) == 2
        assert r.assertions[0].rule_id == "RULE-01"
        assert r.assertions[0].severity == "ERROR"
        assert r.assertions[0].is_report is False
        assert r.assertions[1].rule_id == "RULE-02"
        assert r.assertions[1].severity == "WARNING"
        assert r.assertions[1].is_report is True

        schema_bytes = parse_schematron(sch_xml.encode("utf-8"))
        assert schema_bytes.title == "Test Schema"

    def test_parse_invalid_root(self) -> None:
        with pytest.raises(ValueError, match="Root element must be 'schema'"):
            parse_schematron("<not-schema></not-schema>")

    def test_parse_unsupported_type(self) -> None:
        with pytest.raises(
            ValueError, match="Unsupported Schematron source type"
        ):
            parse_schematron(12345)  # type: ignore[arg-type]

    def test_resolve_rulebook_errors(self) -> None:
        with pytest.raises(FileNotFoundError):
            resolve_rulebook_path("non_existent_rulebook.sch")

        with patch.dict(PRESET_RULEBOOKS, {"missing": "non_existent.sch"}):
            with pytest.raises(FileNotFoundError, match="missing from"):
                resolve_rulebook_path("missing")


class TestSchematronEvaluator:
    """Test XPath context resolution and assertion evaluation."""

    def test_local_tag_and_matching(self) -> None:
        assert _local_tag("{urn:test}Elem") == "Elem"
        assert _local_tag("Simple") == "Simple"

        elem = ET.Element("{urn:test}Elem")
        assert _match_tag(elem, "*", {}) is True
        assert _match_tag(elem, "test:Elem", {"test": "urn:test"}) is True
        assert _match_tag(elem, "Elem", {}) is True
        assert _match_tag(elem, "Other", {}) is False

    def test_find_context_elements(self) -> None:
        root = ET.fromstring(SAMPLE_SEPA_XML)
        ns = {"pain": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}

        # Root contexts
        assert len(find_context_elements(root, ".", ns)) == 1
        assert len(find_context_elements(root, "/", ns)) == 1

        # Descendant context
        cdt_elements = find_context_elements(root, "//pain:CdtTrfTxInf", ns)
        assert len(cdt_elements) == 1
        assert _local_tag(cdt_elements[0].tag) == "CdtTrfTxInf"

        pmt_elements = find_context_elements(root, "//pain:PmtInf", ns)
        assert len(pmt_elements) == 1

        # Direct path from root
        path_elements = find_context_elements(
            root, "CstmrCdtTrfInitn/PmtInf", ns
        )
        assert len(path_elements) == 1

    def test_resolve_xpath_value(self) -> None:
        root = ET.fromstring(SAMPLE_SEPA_XML)
        ns = {"pain": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
        tx = find_context_elements(root, "//pain:CdtTrfTxInf", ns)[0]
        pmt = find_context_elements(root, "//pain:PmtInf", ns)[0]

        # Attribute resolution
        ccy = resolve_xpath_value(tx, "pain:Amt/pain:InstdAmt/@Ccy", ns)
        assert ccy == "EUR"

        # Missing attribute
        assert (
            resolve_xpath_value(tx, "pain:Amt/pain:InstdAmt/@NonExistent", ns)
            is None
        )

        # Element text resolution
        chrgb = resolve_xpath_value(pmt, "pain:ChrgBr", ns)
        assert chrgb == "SLEV"

        # Current element text
        assert resolve_xpath_value(tx, ".", ns) == ""

        # Non existent path
        assert resolve_xpath_value(tx, "pain:NonExistent/Child", ns) is None

    def test_tokenize(self) -> None:
        tokens = _tokenize(
            "pain:Amt/pain:InstdAmt/@Ccy = 'EUR' and (number(pain:Amt) <= 1000)"
        )
        assert "pain:Amt/pain:InstdAmt/@Ccy" in tokens
        assert "=" in tokens
        assert "'EUR'" in tokens
        assert "and" in tokens
        assert "(" in tokens
        assert "<=" in tokens
        assert "1000" in tokens

    def test_xpath_evaluator_comparisons(self) -> None:
        root = ET.fromstring(SAMPLE_SEPA_XML)
        ns = {"pain": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
        tx = find_context_elements(root, "//pain:CdtTrfTxInf", ns)[0]
        evaluator = XPathEvaluator(tx, ns)

        assert (
            evaluator.evaluate("pain:Amt/pain:InstdAmt/@Ccy = 'EUR'") is True
        )
        assert (
            evaluator.evaluate("pain:Amt/pain:InstdAmt/@Ccy != 'USD'") is True
        )
        assert (
            evaluator.evaluate("number(pain:Amt/pain:InstdAmt) > 200") is True
        )
        assert (
            evaluator.evaluate("number(pain:Amt/pain:InstdAmt) <= 250.75")
            is True
        )
        assert (
            evaluator.evaluate("number(pain:Amt/pain:InstdAmt) < 100") is False
        )
        assert (
            evaluator.evaluate("number(pain:Amt/pain:InstdAmt) >= 300")
            is False
        )

        # Boolean and or
        assert (
            evaluator.evaluate(
                "pain:PmtId/pain:EndToEndId = 'E2E-12345' and pain:Amt/pain:InstdAmt/@Ccy = 'EUR'"
            )
            is True
        )
        assert (
            evaluator.evaluate(
                "pain:Amt/pain:InstdAmt/@Ccy = 'USD' or pain:Amt/pain:InstdAmt/@Ccy = 'EUR'"
            )
            is True
        )
        assert (
            evaluator.evaluate(
                "pain:Amt/pain:InstdAmt/@Ccy = 'USD' or pain:Amt/pain:InstdAmt/@Ccy = 'GBP'"
            )
            is False
        )

        # String functions
        assert (
            evaluator.evaluate(
                "string-length(pain:CdtrAgt/pain:FinInstnId/pain:BIC) = 11"
            )
            is True
        )
        assert (
            evaluator.evaluate(
                "starts-with(pain:CdtrAcct/pain:Id/pain:IBAN, 'FR')"
            )
            is True
        )
        assert (
            evaluator.evaluate(
                "contains(pain:CdtrAcct/pain:Id/pain:IBAN, '00003')"
            )
            is True
        )

        # Booleans and not
        assert (
            evaluator.evaluate("boolean(pain:CdtrAcct/pain:Id/pain:IBAN)")
            is True
        )
        assert evaluator.evaluate("not(pain:NonExistent)") is True
        assert evaluator.evaluate("true()") is True
        assert evaluator.evaluate("false()") is False

        # Empty expression
        assert evaluator.evaluate("") is True

    def test_assertion_evaluation(self) -> None:
        root = ET.fromstring(SAMPLE_SEPA_XML)
        ns = {"pain": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
        tx = find_context_elements(root, "//pain:CdtTrfTxInf", ns)[0]

        # Passing assertion
        assert_pass = SchematronAssertion(
            rule_id="TEST-PASS",
            test="pain:Amt/pain:InstdAmt/@Ccy = 'EUR'",
            message="Currency must be EUR",
        )
        assert (
            evaluate_assertion(assert_pass, tx, "//pain:CdtTrfTxInf", ns)
            is None
        )

        # Failing assertion
        assert_fail = SchematronAssertion(
            rule_id="TEST-FAIL",
            test="pain:Amt/pain:InstdAmt/@Ccy = 'USD'",
            message="Currency must be USD",
        )
        viol = evaluate_assertion(assert_fail, tx, "//pain:CdtTrfTxInf", ns)
        assert viol is not None
        assert viol.rule_id == "TEST-FAIL"

        # Report (fails if test is True)
        report_fail = SchematronAssertion(
            rule_id="REPORT-FAIL",
            test="pain:Amt/pain:InstdAmt/@Ccy = 'EUR'",
            message="Report: EUR currency detected",
            is_report=True,
        )
        viol_rep = evaluate_assertion(
            report_fail, tx, "//pain:CdtTrfTxInf", ns
        )
        assert viol_rep is not None
        assert viol_rep.rule_id == "REPORT-FAIL"


class TestSchematronValidatorPresets:
    """Test validation against built-in EPC SEPA, FedNow, and CBPR+ rulebooks."""

    def test_validate_sepa_clean(self) -> None:
        res = validate_schematron(SAMPLE_SEPA_XML, rulebook="sepa")
        assert res.is_valid is True
        assert res.error_count == 0
        assert res.rules_evaluated > 0

    def test_validate_sepa_violations(self) -> None:
        # Mutate to violate currency and charge bearer
        invalid_xml = SAMPLE_SEPA_XML.replace(
            'Ccy="EUR"', 'Ccy="USD"'
        ).replace("<ChrgBr>SLEV</ChrgBr>", "<ChrgBr>DEBT</ChrgBr>")
        res = validate_schematron(invalid_xml, rulebook="sepa")
        assert res.is_valid is False
        assert res.error_count >= 2
        rule_ids = [v.rule_id for v in res.violations]
        assert "EPC-SCT-001" in rule_ids
        assert "EPC-PMT-003" in rule_ids

    def test_validate_fednow_clean(self) -> None:
        res = validate_schematron(SAMPLE_FEDNOW_XML, rulebook="fednow")
        assert res.is_valid is True
        assert res.error_count == 0

    def test_validate_fednow_violations(self) -> None:
        invalid_fednow = SAMPLE_FEDNOW_XML.replace(
            'Ccy="USD"', 'Ccy="EUR"'
        ).replace("50000.00", "2000000.00")
        res = validate_schematron(invalid_fednow, rulebook="fednow")
        assert res.is_valid is False
        rule_ids = [v.rule_id for v in res.violations]
        assert "FDN-TX-001" in rule_ids
        assert "FDN-TX-004" in rule_ids

    def test_validate_cbpr_clean(self) -> None:
        res = validate_schematron(SAMPLE_CBPR_XML, rulebook="cbpr")
        assert res.is_valid is True
        assert res.error_count == 0

    def test_validate_cbpr_violations(self) -> None:
        invalid_cbpr = SAMPLE_CBPR_XML.replace(
            "c56a4180-65aa-42ec-a945-5fd21dec0538", "bad-uetr"
        )
        res = validate_schematron(invalid_cbpr, rulebook="cbpr")
        assert res.is_valid is False
        rule_ids = [v.rule_id for v in res.violations]
        assert "CBPR-TX-004" in rule_ids

    def test_validator_input_formats(self) -> None:
        validator = SchematronValidator("sepa")
        # Bytes input
        res_bytes = validator.validate(SAMPLE_SEPA_XML.encode("utf-8"))
        assert res_bytes.is_valid is True

        # Element input
        root = ET.fromstring(SAMPLE_SEPA_XML)
        res_elem = validator.validate(root)
        assert res_elem.is_valid is True

        # Path input
        with tempfile.NamedTemporaryFile(
            "w", suffix=".xml", delete=False
        ) as f:
            f.write(SAMPLE_SEPA_XML)
            f_path = Path(f.name)
        try:
            res_path = validator.validate(f_path)
            assert res_path.is_valid is True
            res_str_path = validator.validate(str(f_path))
            assert res_str_path.is_valid is True
        finally:
            if f_path.exists():
                f_path.unlink()

        # Invalid type
        with pytest.raises(ValueError, match="Unsupported XML input type"):
            validator.validate(42)  # type: ignore[arg-type]


VALID_CSV = (
    "id,date,nb_of_txs,initiator_name,initiator_street_name,initiator_building_number,"
    "initiator_postal_code,initiator_town_name,initiator_country_code,payment_information_id,"
    "payment_method,batch_booking,requested_execution_date,debtor_name,debtor_street_name,"
    "debtor_building_number,debtor_postal_code,debtor_town_name,debtor_country_code,"
    "debtor_account_IBAN,debtor_agent_BIC,charge_bearer,payment_id,payment_amount,currency,"
    "payment_currency,ctrl_sum,creditor_agent_BIC,creditor_name,creditor_street_name,"
    "creditor_building_number,creditor_postal_code,creditor_town_name,creditor_country_code,"
    "creditor_account_IBAN,purpose_code,reference_number,reference_date,service_level_code,"
    "forwarding_agent_BIC,remittance_information,charge_account_IBAN\n"
    "1,2023-03-10T15:30:47.000Z,1,John Doe,John's Street,1,12345,John's Town,DE,"
    "Payment-Info-12345,TRF,true,2023-03-12,Acme Corp,Acme Street,2,67890,Acme Town,DE,"
    "DE07512108001245126162,BANKDEFFXXX,SLEV,PaymentID6789,150,EUR,EUR,150,SPUEDE2UXXX,"
    "Global Tech,Global Street,3,11223,Global Town,DE,DE36210501700024690959,OTHR,"
    "Invoice-98765,2023-03-09,SEPA,SPUEDE2UXXX,Invoice-12345,DE77100000000000000000\n"
)

INVALID_SEPA_CSV = (
    "id,date,nb_of_txs,initiator_name,initiator_street_name,initiator_building_number,"
    "initiator_postal_code,initiator_town_name,initiator_country_code,payment_information_id,"
    "payment_method,batch_booking,requested_execution_date,debtor_name,debtor_street_name,"
    "debtor_building_number,debtor_postal_code,debtor_town_name,debtor_country_code,"
    "debtor_account_IBAN,debtor_agent_BIC,charge_bearer,payment_id,payment_amount,currency,"
    "payment_currency,ctrl_sum,creditor_agent_BIC,creditor_name,creditor_street_name,"
    "creditor_building_number,creditor_postal_code,creditor_town_name,creditor_country_code,"
    "creditor_account_IBAN,purpose_code,reference_number,reference_date,service_level_code,"
    "forwarding_agent_BIC,remittance_information,charge_account_IBAN\n"
    "1,2023-03-10T15:30:47.000Z,1,John Doe,John's Street,1,12345,John's Town,DE,"
    "Payment-Info-12345,TRF,true,2023-03-12,Acme Corp,Acme Street,2,67890,Acme Town,DE,"
    "DE07512108001245126162,BANKDEFFXXX,SLEV,PaymentID6789,150,USD,USD,150,SPUEDE2UXXX,"
    "Global Tech,Global Street,3,11223,Global Town,DE,DE36210501700024690959,OTHR,"
    "Invoice-98765,2023-03-09,SEPA,SPUEDE2UXXX,Invoice-12345,DE77100000000000000000\n"
)


class TestSchematronCoreIntegration:
    """Test process_files and process_files_streaming with Schematron validation."""

    def test_process_files_schematron_pass(self) -> None:
        os.makedirs("pain001/tmp", exist_ok=True)
        with tempfile.TemporaryDirectory(dir="pain001/tmp") as tmpdir:
            csv_path = os.path.join(tmpdir, "payments.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(VALID_CSV)
            tpl = "pain001/templates/pain.001.001.03/template.xml"
            xsd = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"
            out_xml = os.path.join(tmpdir, "output.xml")

            written = process_files(
                xml_message_type="pain.001.001.03",
                xml_template_file_path=tpl,
                xsd_schema_file_path=xsd,
                data_file_path=csv_path,
                output_path=out_xml,
                schematron="sepa",
            )
            assert os.path.exists(written)

    def test_process_files_schematron_fail(self) -> None:
        os.makedirs("pain001/tmp", exist_ok=True)
        with tempfile.TemporaryDirectory(dir="pain001/tmp") as tmpdir:
            csv_path = os.path.join(tmpdir, "payments.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(INVALID_SEPA_CSV)
            tpl = "pain001/templates/pain.001.001.03/template.xml"
            xsd = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"
            out_xml = os.path.join(tmpdir, "output.xml")

            with pytest.raises(
                XMLGenerationError,
                match="Schematron rulebook validation failed",
            ):
                process_files(
                    xml_message_type="pain.001.001.03",
                    xml_template_file_path=tpl,
                    xsd_schema_file_path=xsd,
                    data_file_path=csv_path,
                    output_path=out_xml,
                    schematron="sepa",
                )

    def test_process_files_streaming_schematron(self) -> None:
        os.makedirs("pain001/tmp", exist_ok=True)
        with tempfile.TemporaryDirectory(dir="pain001/tmp") as tmpdir:
            csv_path = os.path.join(tmpdir, "payments.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(VALID_CSV)
            tpl = "pain001/templates/pain.001.001.03/template.xml"
            xsd = "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"

            # Streaming pass
            paths = process_files_streaming(
                xml_message_type="pain.001.001.03",
                xml_template_file_path=tpl,
                xsd_schema_file_path=xsd,
                data_file_path=csv_path,
                chunk_size=10,
                output_dir=tmpdir,
                schematron="sepa",
            )
            assert len(paths) == 1
            assert os.path.exists(paths[0])

            # Streaming fail with USD
            bad_csv = os.path.join(tmpdir, "bad.csv")
            with open(bad_csv, "w", encoding="utf-8") as f:
                f.write(INVALID_SEPA_CSV)
            with pytest.raises(
                XMLGenerationError,
                match="Schematron validation failed for chunk",
            ):
                process_files_streaming(
                    xml_message_type="pain.001.001.03",
                    xml_template_file_path=tpl,
                    xsd_schema_file_path=xsd,
                    data_file_path=bad_csv,
                    chunk_size=10,
                    output_dir=tmpdir,
                    schematron="sepa",
                )


class TestSchematronCliIntegration:
    """Test CLI commands with --schematron flag."""

    def test_cli_validate_schematron_pass(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "payments.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(VALID_CSV)
            result = runner.invoke(
                cli,
                [
                    "validate",
                    "-t",
                    "pain.001.001.03",
                    "-d",
                    csv_path,
                    "--schematron",
                    "sepa",
                ],
            )
            assert result.exit_code == 0
            assert "Schematron rulebook 'sepa' passed" in result.output

    def test_cli_validate_schematron_fail(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "bad.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(INVALID_SEPA_CSV)
            result = runner.invoke(
                cli,
                [
                    "validate",
                    "-t",
                    "pain.001.001.03",
                    "-d",
                    csv_path,
                    "--schematron",
                    "sepa",
                ],
            )
            assert result.exit_code == 1
            assert "Schematron rulebook 'sepa' failed" in result.output
            assert "EPC-SCT-001" in result.output


class TestSchematronExhaustiveCoverage:
    """Exhaustive tests for 100% line and branch coverage across schematron package."""

    def test_models_branches(self) -> None:
        v = SchematronViolation(
            rule_id="TEST-001",
            message="No remediation violation",
            context="//node",
            test="false()",
            severity="ERROR",
            line_number=42,
        )
        object.__setattr__(v, "remediation", "")
        res = SchematronValidationResult(
            is_valid=False,
            rulebook="test",
            violations=[v],
            rules_evaluated=1,
            rules_passed=0,
            duration_ms=1.0,
        )
        # Test line_number and missing remediation branch in format_report
        detailed_report = res.format_report(detailed=True)
        assert "[Line 42]" in detailed_report
        assert "Fix:" not in detailed_report

        # Test non-detailed report branch
        summary_report = res.format_report(detailed=False)
        assert "FAILED" in summary_report
        assert "Violations:" not in summary_report

    def test_validator_path_object(self) -> None:
        p = Path("pain001/schematron/rules/epc_sepa.sch")
        resolved = resolve_rulebook_path(p)
        assert resolved == p.resolve()

    def test_parser_string_path_and_edge_nodes(self) -> None:
        # String path (not starting with '<')
        schema_from_path = parse_schematron(
            "pain001/schematron/rules/epc_sepa.sch"
        )
        assert len(schema_from_path.patterns) >= 1

        # XML with ns missing prefix or uri, other children in schema/pattern/rule, rule without assertions
        sch_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <schema xmlns="http://purl.oclc.org/dsdl/schematron">
            <title>Edge Test</title>
            <p>Direct schema comment/child</p>
            <ns prefix="" uri="urn:empty-prefix"/>
            <ns prefix="test" uri=""/>
            <ns prefix="valid" uri="urn:valid"/>
            <pattern id="P1">
                <title>P1 Title</title>
                <p>Ignored pattern child</p>
                <rule context="//valid:Node">
                    <p>Ignored rule child</p>
                    <assert test="true()" id="R1">Valid assert</assert>
                    <report test="false()" id="R2" role="warn"></report>
                </rule>
                <rule context="//valid:EmptyRule">
                    <p>No assertions here</p>
                </rule>
            </pattern>
        </schema>
        """
        parsed = parse_schematron(sch_xml)
        assert "valid" in parsed.namespaces
        assert len(parsed.patterns) == 1
        assert len(parsed.patterns[0].rules) == 1
        assert len(parsed.patterns[0].rules[0].assertions) == 2
        # Check fallback message for empty assertion text
        assert (
            "Assertion R2 failed"
            in parsed.patterns[0].rules[0].assertions[1].message
        )

    def test_evaluator_branches(self) -> None:
        elem_no_ns = ET.Element("BareElement")
        assert _match_tag(elem_no_ns, "BareElement", {}) is True
        assert _match_tag(elem_no_ns, "Other", {}) is False

        root = ET.Element("Document")
        child = ET.SubElement(root, "Child")
        leaf = ET.SubElement(child, "Leaf")
        leaf.text = "Hello"

        # find_context_elements empty steps branch
        assert find_context_elements(root, "///", {}) == [root]

        # find_context_elements root matches first step
        found = find_context_elements(root, "Document/Child/Leaf", {})
        assert len(found) == 1
        assert found[0] == leaf

        # resolve_xpath_value with empty text element
        ET.SubElement(root, "Empty")
        assert resolve_xpath_value(root, "Empty", {}) == ""
        assert resolve_xpath_value(root, "NonExistent/Deep", {}) is None

        # XPathEvaluator comparisons
        evaluator = XPathEvaluator(leaf, {})

        # Numeric inequality
        tokens_num_neq_t = _tokenize("1 != 2")
        val, _ = evaluator._eval_comparison(tokens_num_neq_t, 0)
        assert val is True

        tokens_num_neq_f = _tokenize("2 != 2")
        val, _ = evaluator._eval_comparison(tokens_num_neq_f, 0)
        assert val is False

        # String comparisons <, <=, >, >=
        for expr, expected in [
            ("'alpha' < 'beta'", True),
            ("'beta' < 'alpha'", False),
            ("'alpha' <= 'alpha'", True),
            ("'beta' > 'alpha'", True),
            ("'alpha' > 'beta'", False),
            ("'beta' >= 'beta'", True),
        ]:
            toks = _tokenize(expr)
            val, _ = evaluator._eval_comparison(toks, 0)
            assert val is expected, f"Failed for {expr}"

        # Unknown operator in _apply_comparison
        assert evaluator._apply_comparison(1, "INVALID", 2) is False

        # Parenthesized expression and constants
        assert evaluator.evaluate("(1 = 1) and true()") is True
        assert evaluator.evaluate("false() or (2 = 2)") is True
        assert evaluator.evaluate("(1 = 1") is True  # unclosed parenthesis

        # Functions: number('invalid'), count, unknown function, empty args
        assert evaluator.evaluate("number('not_a_num') = 0") is True
        child_eval = XPathEvaluator(child, {})
        assert child_eval.evaluate("count(Leaf) = 1") is True
        assert child_eval.evaluate("count(Missing) = 0") is True
        assert evaluator.evaluate("starts-with('hello', 'he')") is True
        assert (
            evaluator.evaluate("starts-with('hello', 'he'") is True
        )  # unclosed function
        val_empty_fn, _ = evaluator._eval_function(
            "true", ["fn", "("], 2
        )  # empty tokens after paren
        assert val_empty_fn is True
        assert evaluator.evaluate("contains('hello', 'ell')") is True
        assert evaluator.evaluate("unknown_function(1) = 'test'") is False
        assert evaluator.evaluate("not() and boolean()") is False

        # eval_primary out of range
        out_val, out_idx = evaluator._eval_primary([], 0)
        assert out_val is None
