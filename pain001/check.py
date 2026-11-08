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

"""Check a payment file that already exists (``pain001 check``).

The same ladder the corpus build runs on every file it writes
(ADR-0003), run on a document pain001 did not necessarily produce:

* **xsd**: the bundled schema of the message type the document's
  namespace names;
* **mdr**: the enforced cross-element rules of the message definition
  report;
* **scheme**: the scheme profiles asked for, and a private CEL policy
  when one is given, run on the document's row projection;
* **schematron**: a Schematron rulebook, when one is asked for.

:func:`check_document` returns a :class:`CheckReport`; the CLI, the
REST API and the MCP server render the same report, as text, JSON or
SARIF 2.1.0.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from defusedxml import DefusedXmlException
from defusedxml import ElementTree as defused_et

from pain001.constants import VERSION

#: The largest document check reads: 10 MiB, as for an inline document
#: in the faces engine and an upload in the web UI.
MAX_CHECK_BYTES = 10 * 1024 * 1024

_NAMESPACE = re.compile(
    r"^\{urn:iso:std:iso:20022:tech:xsd:(pain\.00[18]\.001\.\d{2})\}Document$"
)

# A namespace in Clark notation ({uri}), dropped from XSD messages: every
# element of a checked document is in the one message namespace.
_CLARK = re.compile(r"\{[^}]*\}")

#: Rung names, in the order they run.
RUNGS = ("xsd", "mdr", "scheme", "schematron")


class NotAPaymentDocument(ValueError):
    """Well-formed XML whose root is not a pain.001 or pain.008 Document."""


@dataclass(frozen=True)
class CheckFinding:
    """One problem one rung found.

    Attributes:
        rung: ``xsd``, ``mdr``, ``scheme`` or ``schematron``.
        rule: The rule id (the rung's name for XSD findings).
        severity: ``error`` or ``warning``.
        message: What is wrong.
        location: Where: an element path, a Schematron context, or
            ``transaction N`` for a scheme finding on a row.
    """

    rung: str
    rule: str
    severity: str
    message: str
    location: str | None = None


@dataclass(frozen=True)
class CheckReport:
    """The result of checking one document.

    Attributes:
        message_type: The message type the namespace names.
        rungs: The rungs that ran, in order.
        findings: Every finding, in rung order.
    """

    message_type: str
    rungs: tuple[str, ...]
    findings: tuple[CheckFinding, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> int:
        """How many error-severity findings there are."""
        return sum(f.severity == "error" for f in self.findings)

    @property
    def warnings(self) -> int:
        """How many warning-severity findings there are."""
        return sum(f.severity != "error" for f in self.findings)

    @property
    def passed(self) -> bool:
        """True when no rung found an error."""
        return self.errors == 0

    def as_dict(self) -> dict[str, Any]:
        """A JSON-ready form of the report."""
        return {
            "message_type": self.message_type,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "rungs": list(self.rungs),
            "findings": [asdict(f) for f in self.findings],
        }


def detect_message_type(xml: str) -> str:
    """The pain.001 or pain.008 message type a document's root declares.

    Args:
        xml: The document.

    Returns:
        The message type, for example ``pain.001.001.09``.

    Raises:
        NotAPaymentDocument: If the root is not a pain.001 or pain.008
            ``Document``.
        ValueError: If the document is not well-formed XML, carries a DTD,
            or names a version pain001 does not bundle.
    """
    from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

    try:
        root = defused_et.fromstring(xml)
    except defused_et.ParseError as exc:
        raise ValueError(f"not well-formed XML: {exc}") from exc
    except DefusedXmlException as exc:
        raise ValueError(
            f"refused: DTDs and entities are not allowed ({exc!r})"
        ) from exc
    match = _NAMESPACE.match(root.tag)
    if match is None:
        raise NotAPaymentDocument(
            f"not a pain.001 or pain.008 Document: the root is {root.tag}"
        )
    message_type = match[1]
    if message_type not in DEFAULT_TEMPLATE_REGISTRY.list_supported_versions():
        raise ValueError(
            f"{message_type} is not a message type pain001 bundles"
        )
    return message_type


def _xsd(xml: str, message_type: str) -> list[CheckFinding]:
    """The XSD rung: one finding per schema violation, namespaces dropped."""
    from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
    from pain001.xml.validate_via_xsd import collect_xsd_validation_errors

    xsd = DEFAULT_TEMPLATE_REGISTRY.get_template(message_type).xsd_path
    findings = []
    for raw in collect_xsd_validation_errors(xml, str(xsd), max_errors=50):
        text = _CLARK.sub("", raw)
        path, _, reason = text.partition(": ")
        location = path if reason else None
        findings.append(
            CheckFinding("xsd", "xsd", "error", reason or text, location)
        )
    return findings


def _mdr(xml: str) -> list[CheckFinding]:
    """The MDR rung: every enforced cross-element rule the document breaks."""
    from pain001.corpus.rules.mdr import evaluate_mdr

    return [
        CheckFinding("mdr", f.rule_id, "error", f.message, f.path)
        for f in evaluate_mdr(xml)
    ]


def _scheme(
    xml: str, message_type: str, scheme: str | None, policy: str | None
) -> list[CheckFinding]:
    """The scheme rung: profiles, or a policy with them, on the rows."""
    from pain001.corpus.rules.projection import rows_from_xml
    from pain001.validation.schemes import validate_scheme

    rows = rows_from_xml(xml)
    if policy is not None:
        from pain001.validation.policy import validate_policy

        result = validate_policy(rows, policy, scheme, message_type)
    else:
        result = validate_scheme(rows, str(scheme), message_type=message_type)
    return [
        CheckFinding(
            "scheme",
            v.rule,
            "error" if v.severity == "error" else "warning",
            v.message,
            f"transaction {v.index + 1}" + (f", {v.field}" if v.field else ""),
        )
        for v in result.violations
    ]


def _schematron(xml: str, rulebook: str) -> list[CheckFinding]:
    """The Schematron rung: one finding per failed assertion."""
    from pain001.schematron import validate_schematron

    result = validate_schematron(xml, rulebook=rulebook)
    return [
        CheckFinding(
            "schematron",
            v.rule_id,
            "error" if v.severity == "ERROR" else "warning",
            v.message,
            v.context,
        )
        for v in result.violations
    ]


def check_document(
    xml: str | bytes,
    *,
    scheme: str | None = None,
    policy: str | None = None,
    schematron: str | None = None,
) -> CheckReport:
    """Run the validation ladder on one existing document.

    Args:
        xml: The document, as text or UTF-8 bytes.
        scheme: Scheme profile names, comma-separated (``sepa-sct``).
        policy: The text of a private CEL policy file
            (``pain001[rules]``); it runs with the scheme profiles.
        schematron: A Schematron preset (``sepa``, ``fednow``, ``cbpr``)
            or the path of a ``.sch`` file.

    Returns:
        The report. A document that fails the XSD still gets the MDR
        and scheme rungs, so every problem is reported in one pass.

    Raises:
        ValueError: If the document is too large, not a bundled pain.001
            or pain.008 message, or a scheme, policy or rulebook named is
            unknown or invalid.
    """
    if isinstance(xml, bytes):
        if len(xml) > MAX_CHECK_BYTES:
            raise ValueError("document exceeds the 10 MiB check limit")
        xml = xml.decode("utf-8")
    elif len(xml.encode("utf-8")) > MAX_CHECK_BYTES:
        raise ValueError("document exceeds the 10 MiB check limit")
    message_type = detect_message_type(xml)
    rungs = ["xsd", "mdr"]
    findings = _xsd(xml, message_type) + _mdr(xml)
    if scheme or policy is not None:
        rungs.append("scheme")
        findings += _scheme(xml, message_type, scheme, policy)
    if schematron:
        rungs.append("schematron")
        findings += _schematron(xml, schematron)
    return CheckReport(message_type, tuple(rungs), tuple(findings))


def format_text(report: CheckReport, name: str) -> str:
    """The report as plain text, one finding per line.

    Args:
        report: The report.
        name: The file name to show.

    Returns:
        The text, ending with a one-line verdict.
    """
    lines = [
        f"{name}: {f.severity} [{f.rung}] {f.rule}"
        + (f" at {f.location}" if f.location else "")
        + f": {f.message}"
        for f in report.findings
    ]
    verdict = "passed" if report.passed else "failed"
    lines.append(
        f"{name}: {report.message_type} {verdict} "
        f"({', '.join(report.rungs)}): {report.errors} error(s), "
        f"{report.warnings} warning(s)"
    )
    return "\n".join(lines)


def to_sarif(checked: Sequence[tuple[CheckReport, str]]) -> dict[str, Any]:
    """Reports as one SARIF 2.1.0 log, for code scanning.

    Args:
        checked: Each report with the checked file's path, relative to
            the repository root when the log is uploaded to code
            scanning.

    Returns:
        The SARIF log as a JSON-ready dict: one run, one rule per
        ``rung/rule`` id, one result per finding.
    """
    rule_ids = sorted(
        {
            f"{f.rung}/{f.rule}"
            for report, _ in checked
            for f in report.findings
        }
    )
    results = [
        _sarif_result(finding, uri, rule_ids)
        for report, uri in checked
        for finding in report.findings
    ]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "pain001 check",
                        "version": VERSION,
                        "informationUri": "https://pain001.com",
                        "rules": [{"id": rule} for rule in rule_ids],
                    }
                },
                "results": results,
            }
        ],
    }


def _sarif_result(
    finding: CheckFinding, uri: str, rule_ids: list[str]
) -> dict[str, Any]:
    """One finding as a SARIF result on the checked file."""
    rule_id = f"{finding.rung}/{finding.rule}"
    where = f" (at {finding.location})" if finding.location else ""
    return {
        "ruleId": rule_id,
        "ruleIndex": rule_ids.index(rule_id),
        "level": "error" if finding.severity == "error" else "warning",
        "message": {"text": finding.message + where},
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri}}}
        ],
    }


__all__ = [
    "MAX_CHECK_BYTES",
    "RUNGS",
    "CheckFinding",
    "CheckReport",
    "NotAPaymentDocument",
    "check_document",
    "detect_message_type",
    "format_text",
    "to_sarif",
]
