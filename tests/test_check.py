# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""``pain001.check``: the validation ladder on an existing document."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pain001 import check
from pain001.check import (
    MAX_CHECK_BYTES,
    CheckFinding,
    CheckReport,
    NotAPaymentDocument,
    check_document,
    detect_message_type,
    format_text,
    to_sarif,
)
from pain001.corpus.rules.mdr import MdrFinding

COVERAGE = Path(check.__file__).parent / "corpus" / "data" / "coverage"
EVERY_EDITION = sorted(path.name for path in COVERAGE.iterdir())
V09 = (
    COVERAGE / "pain.001.001.09" / "01-transfer-every-element.xml"
).read_text(encoding="utf-8")


def _first(edition: str) -> bytes:
    return sorted((COVERAGE / edition).glob("*.xml"))[0].read_bytes()


@pytest.mark.parametrize("edition", EVERY_EDITION)
def test_every_bundled_edition_passes_the_default_ladder(edition: str) -> None:
    report = check_document(_first(edition))
    assert report.message_type == edition
    assert report.rungs == ("xsd", "mdr")
    assert report.passed, report.findings


def test_text_and_bytes_give_the_same_report() -> None:
    assert check_document(V09) == check_document(V09.encode("utf-8"))


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ("<Document", "not well-formed XML"),
        ("<root/>", "not a pain.001 or pain.008 Document"),
        (
            '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:'
            'pain.002.001.10"/>',
            "not a pain.001 or pain.008 Document",
        ),
        (
            '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:'
            'pain.001.001.99"/>',
            "pain.001.001.99 is not a message type pain001 bundles",
        ),
    ],
)
def test_a_document_that_is_not_a_bundled_message_is_refused(
    document: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        detect_message_type(document)


@pytest.mark.parametrize(
    "document",
    [b"<" * (MAX_CHECK_BYTES + 1), "<" * (MAX_CHECK_BYTES + 1)],
    ids=["bytes", "text"],
)
def test_an_oversized_document_is_refused(document: str | bytes) -> None:
    with pytest.raises(ValueError, match="10 MiB"):
        check_document(document)


def test_a_dtd_is_refused_not_expanded() -> None:
    with pytest.raises(ValueError, match="DTDs and entities are not allowed"):
        check_document('<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')


def test_an_xsd_error_names_the_element_without_namespaces() -> None:
    bad = V09.replace("<NbOfTxs>", "<Foo>x</Foo><NbOfTxs>", 1)
    report = check_document(bad)
    assert not report.passed
    (finding,) = report.findings
    assert finding.rung == "xsd"
    assert finding.rule == "xsd"
    assert finding.location == "/Document/CstmrCdtTrfInitn/GrpHdr"
    assert "Foo" in finding.message
    assert "urn:iso" not in finding.message


def test_an_xsd_message_without_a_path_keeps_its_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pain001.xml.validate_via_xsd.collect_xsd_validation_errors",
        lambda *_, **__: ["XML parse error"],
    )
    (finding,) = check._xsd(V09, "pain.001.001.09")
    assert (finding.message, finding.location) == ("XML parse error", None)


def test_mdr_findings_carry_rule_and_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pain001.corpus.rules.mdr.evaluate_mdr",
        lambda _: [MdrFinding("ChequeInstructionRule", "/Document/x", "why")],
    )
    report = check_document(V09)
    assert report.findings == (
        CheckFinding(
            "mdr", "ChequeInstructionRule", "error", "why", "/Document/x"
        ),
    )


def test_a_scheme_runs_on_the_row_projection() -> None:
    report = check_document(V09, scheme="sepa-sct")
    assert report.rungs == ("xsd", "mdr", "scheme")
    rules = {f.rule: f for f in report.findings}
    assert rules["SEPA-CHRGBR"].severity == "error"
    assert rules["SEPA-CHRGBR"].location == "transaction 1, charge_bearer"
    assert rules["SEPA-SVCLVL"].severity == "warning"
    assert report.errors >= 1 and report.warnings >= 1
    assert not report.passed


def test_an_unknown_scheme_is_refused() -> None:
    with pytest.raises(ValueError, match="no-such-scheme"):
        check_document(V09, scheme="no-such-scheme")


def test_a_policy_runs_with_the_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str | None, str]] = []

    def fake_policy(
        rows: list[dict[str, str]],
        source: str,
        profile: str | None,
        message_type: str,
    ) -> object:
        seen.append((source, profile, message_type))
        from pain001.validation._scheme_types import (
            SchemeValidationResult,
            SchemeViolation,
        )

        return SchemeValidationResult(
            "policy", [SchemeViolation("P-1", "no", 0)]
        )

    monkeypatch.setattr(
        "pain001.validation.policy.validate_policy", fake_policy
    )
    report = check_document(V09, policy="rules: []")
    assert seen == [("rules: []", None, "pain.001.001.09")]
    assert report.findings[-1] == CheckFinding(
        "scheme", "P-1", "error", "no", "transaction 1"
    )


def test_a_schematron_rulebook_runs_on_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pain001.schematron.models import (
        SchematronValidationResult,
        SchematronViolation,
    )

    def fake(xml: str, rulebook: str) -> SchematronValidationResult:
        assert rulebook == "sepa"
        return SchematronValidationResult(
            False,
            "sepa",
            [
                SchematronViolation("EPC-1", "bad", "/Document/a", "t"),
                SchematronViolation(
                    "EPC-2", "meh", "/Document/b", "t", severity="WARNING"
                ),
            ],
            rules_evaluated=2,
        )

    monkeypatch.setattr("pain001.schematron.validate_schematron", fake)
    report = check_document(V09, schematron="sepa")
    assert report.rungs == ("xsd", "mdr", "schematron")
    assert report.findings == (
        CheckFinding("schematron", "EPC-1", "error", "bad", "/Document/a"),
        CheckFinding("schematron", "EPC-2", "warning", "meh", "/Document/b"),
    )


def test_the_real_sepa_rulebook_runs() -> None:
    report = check_document(V09, schematron="sepa")
    assert "schematron" in report.rungs


_REPORT = CheckReport(
    "pain.001.001.09",
    ("xsd", "mdr", "scheme"),
    (
        CheckFinding("xsd", "xsd", "error", "bad element", "/Document/a"),
        CheckFinding("scheme", "SEPA-X", "warning", "hm", None),
        CheckFinding("scheme", "SEPA-X", "error", "again", "transaction 2"),
    ),
)


def test_as_dict_is_json_ready() -> None:
    data = json.loads(json.dumps(_REPORT.as_dict()))
    assert data["passed"] is False
    assert (data["errors"], data["warnings"]) == (2, 1)
    assert data["rungs"] == ["xsd", "mdr", "scheme"]
    assert data["findings"][1] == {
        "rung": "scheme",
        "rule": "SEPA-X",
        "severity": "warning",
        "message": "hm",
        "location": None,
    }


def test_format_text_lists_each_finding_then_the_verdict() -> None:
    verdict = (
        "pay.xml: pain.001.001.09 failed (xsd, mdr, scheme): "
        "2 error(s), 1 warning(s)"
    )
    assert format_text(_REPORT, "pay.xml").splitlines() == [
        "pay.xml: error [xsd] xsd at /Document/a: bad element",
        "pay.xml: warning [scheme] SEPA-X: hm",
        "pay.xml: error [scheme] SEPA-X at transaction 2: again",
        verdict,
    ]
    clean = CheckReport("pain.001.001.09", ("xsd", "mdr"))
    assert format_text(clean, "ok.xml") == (
        "ok.xml: pain.001.001.09 passed (xsd, mdr): 0 error(s), 0 warning(s)"
    )


def test_sarif_is_a_2_1_0_log_with_one_rule_per_id() -> None:
    log = to_sarif([(_REPORT, "payments/pay.xml")])
    assert log["version"] == "2.1.0"
    (run,) = log["runs"]
    driver = run["tool"]["driver"]
    assert driver["name"] == "pain001 check"
    assert [r["id"] for r in driver["rules"]] == ["scheme/SEPA-X", "xsd/xsd"]
    levels = [
        (r["ruleId"], r["ruleIndex"], r["level"]) for r in run["results"]
    ]
    assert levels == [
        ("xsd/xsd", 1, "error"),
        ("scheme/SEPA-X", 0, "warning"),
        ("scheme/SEPA-X", 0, "error"),
    ]
    assert run["results"][0]["message"]["text"] == (
        "bad element (at /Document/a)"
    )
    assert run["results"][1]["message"]["text"] == "hm"
    uri = run["results"][2]["locations"][0]["physicalLocation"][
        "artifactLocation"
    ]["uri"]
    assert uri == "payments/pay.xml"
    json.dumps(log)


def test_one_sarif_run_covers_every_file() -> None:
    clean = CheckReport("pain.001.001.09", ("xsd", "mdr"))
    log = to_sarif([(_REPORT, "a.xml"), (clean, "b.xml"), (_REPORT, "c.xml")])
    (run,) = log["runs"]
    uris = [
        r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        for r in run["results"]
    ]
    assert uris == ["a.xml"] * 3 + ["c.xml"] * 3
    assert to_sarif([])["runs"][0]["results"] == []


def test_a_foreign_root_is_its_own_refusal() -> None:
    with pytest.raises(NotAPaymentDocument):
        detect_message_type("<project/>")
    assert issubclass(NotAPaymentDocument, ValueError)


def test_a_rulebook_that_matches_nothing_is_a_warning() -> None:
    pain008 = (
        COVERAGE / "pain.008.001.08" / "01-collection-every-element.xml"
    ).read_text(encoding="utf-8")
    report = check_document(pain008, schematron="sepa")
    (finding,) = [f for f in report.findings if f.rung == "schematron"]
    assert finding.rule == "no-rules-evaluated"
    assert finding.severity == "warning"
    assert report.passed
