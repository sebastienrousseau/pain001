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

"""Data models and diagnostics for Schematron business rules validation."""

from dataclasses import dataclass, field
from typing import Any

#: Remediation hints for Schematron business rule IDs.
REMEDIATIONS: dict[str, str] = {
    "EPC-SCT-001": "Set currency attribute to 'EUR' on InstdAmt.",
    "EPC-SCT-002": "Set ChrgBr (Charge Bearer) to 'SLEV'.",
    "EPC-SCT-003": "Provide an IBAN for the creditor account.",
    "EPC-SCT-004": "Ensure transaction amount is strictly positive.",
    "EPC-SCT-005": "Reduce transaction amount below 999,999,999.99 EUR.",
    "EPC-SCT-006": (
        "Provide a valid 8 or 11 character BICFI for the creditor agent "
        "or omit it."
    ),
    "EPC-SCT-007": (
        "Provide a non-empty EndToEndId (must not be 'NOTPROVIDED')."
    ),
    "EPC-PMT-001": "Provide an IBAN for the debtor account.",
    "EPC-PMT-002": "Set payment service level code SvcLvl/Cd to 'SEPA'.",
    "EPC-PMT-003": "Set payment level ChrgBr (Charge Bearer) to 'SLEV'.",
    "FDN-TX-001": "Set currency attribute to 'USD' on InstdAmt.",
    "FDN-TX-002": (
        "Set ChrgBr to 'DEBT' or 'SHAR' for FedNow instant transfers."
    ),
    "FDN-TX-003": "Ensure transaction amount is strictly positive.",
    "FDN-TX-004": (
        "Split transfer or reduce amount to stay within FedNow $1,000,000.00 ceiling."
    ),
    "FDN-TX-005": "Provide a unique EndToEndId for the FedNow payment.",
    "FDN-PMT-001": "Specify 'FDN' for clearing system provider or service level.",
    "CBPR-TX-001": "Specify a valid 3-letter ISO 4217 currency code.",
    "CBPR-TX-002": "Ensure transaction amount is strictly positive.",
    "CBPR-TX-003": "Provide a non-empty EndToEndId for cross-border tracing.",
    "CBPR-TX-004": "Ensure UETR matches the 36-character canonical UUID format.",
    "CBPR-TX-005": (
        "Provide a valid 8 or 11 character BICFI for the creditor agent."
    ),
}


def remediation_for(rule_id: str) -> str:
    """Return remediation hint for a Schematron rule ID."""
    return REMEDIATIONS.get(
        rule_id,
        "Review the Schematron assertion test expression and align the XML element.",
    )


@dataclass(frozen=True)
class SchematronViolation:
    """A single rule assertion violation discovered by the Schematron engine.

    Attributes:
        rule_id: Identifying code for the rule (e.g., 'EPC-SCT-001').
        message: Human-readable message explaining the assertion failure.
        context: XPath context where the violation occurred.
        test: The Schematron test expression that evaluated to false.
        line_number: Line number in the XML document if available.
        severity: 'ERROR' or 'WARNING'.
        remediation: Guidance on how to fix the violation.
    """

    rule_id: str
    message: str
    context: str
    test: str
    line_number: int | None = None
    severity: str = "ERROR"
    remediation: str = ""

    def __post_init__(self) -> None:
        if not self.remediation:
            object.__setattr__(
                self, "remediation", remediation_for(self.rule_id)
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert violation to JSON-serializable dictionary."""
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "context": self.context,
            "test": self.test,
            "line_number": self.line_number,
            "severity": self.severity,
            "remediation": self.remediation,
        }


@dataclass
class SchematronValidationResult:
    """The aggregate result of a Schematron rulebook evaluation.

    Attributes:
        is_valid: True if no ERROR-level violations were found.
        rulebook: Name of the evaluated rulebook or schema path.
        violations: List of all violations discovered.
        rules_evaluated: Total count of assertions evaluated.
        rules_passed: Total count of assertions that passed.
        duration_ms: Evaluation duration in milliseconds.
    """

    is_valid: bool
    rulebook: str
    violations: list[SchematronViolation] = field(default_factory=list)
    rules_evaluated: int = 0
    rules_passed: int = 0
    duration_ms: float = 0.0

    @property
    def error_count(self) -> int:
        """Count of ERROR-level violations."""
        return sum(1 for v in self.violations if v.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        """Count of WARNING-level violations."""
        return sum(1 for v in self.violations if v.severity == "WARNING")

    def to_dict(self) -> dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return {
            "is_valid": self.is_valid,
            "rulebook": self.rulebook,
            "rules_evaluated": self.rules_evaluated,
            "rules_passed": self.rules_passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "duration_ms": self.duration_ms,
            "violations": [v.to_dict() for v in self.violations],
        }

    def format_report(self, detailed: bool = True) -> str:
        """Format a human-readable text report of the validation outcome."""
        status = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"Schematron Rulebook: {self.rulebook}",
            f"Status: {status} ({self.rules_passed}/{self.rules_evaluated} rules passed, {self.error_count} errors, {self.warning_count} warnings)",
        ]
        if detailed and self.violations:
            lines.append("\nViolations:")
            for v in self.violations:
                line_str = f" [Line {v.line_number}]" if v.line_number else ""
                lines.append(
                    f"  • [{v.severity}] {v.rule_id}{line_str}: {v.message}"
                )
                lines.append(f"    Context: {v.context}")
                lines.append(f"    Test:    {v.test}")
                if v.remediation:
                    lines.append(f"    Fix:     {v.remediation}")
        return "\n".join(lines)
