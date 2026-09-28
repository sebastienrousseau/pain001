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

"""High-level Schematron validator for ISO 20022 clearing network rulebooks."""

import time
from pathlib import Path
from xml.etree.ElementTree import Element  # nosec B405

from defusedxml import ElementTree as defused_et

from pain001.observability.otel import set_span_attributes, traced
from pain001.schematron.evaluator import (
    evaluate_assertion,
    find_context_elements,
)
from pain001.schematron.models import (
    SchematronValidationResult,
    SchematronViolation,
)
from pain001.schematron.parser import (
    SchematronSchema,
    parse_schematron,
)
from pain001.security.path_validator import validate_path

#: Mapping of friendly preset names to packaged rulebook .sch files.
PRESET_RULEBOOKS: dict[str, str] = {
    "sepa": "epc_sepa.sch",
    "epc-sepa": "epc_sepa.sch",
    "sepa-sct": "epc_sepa.sch",
    "fednow": "fednow.sch",
    "cbpr": "cbpr_plus.sch",
    "cbpr-plus": "cbpr_plus.sch",
    "cbpr+": "cbpr_plus.sch",
    "swift": "cbpr_plus.sch",
}

_RULES_DIR = Path(__file__).resolve().parent / "rules"


def resolve_rulebook_path(rulebook_or_path: str | Path) -> Path:
    """Resolve a rulebook preset name or filesystem path to a Path object.

    Args:
        rulebook_or_path: Friendly name ('sepa', 'fednow') or path to .sch file.

    Returns:
        Resolved Path to the Schematron schema.

    Raises:
        FileNotFoundError: If the specified rulebook or schema cannot be found.
    """
    if isinstance(rulebook_or_path, Path):
        return Path(validate_path(rulebook_or_path, must_exist=True))

    normalized = str(rulebook_or_path).strip().lower()
    if normalized in PRESET_RULEBOOKS:
        preset_file = PRESET_RULEBOOKS[normalized]
        target = _RULES_DIR / preset_file
        if not target.exists():
            raise FileNotFoundError(
                f"Built-in Schematron rulebook '{preset_file}' missing from {_RULES_DIR}"
            )
        return target

    return Path(validate_path(rulebook_or_path, must_exist=True))


class SchematronValidator:
    """Validates ISO 20022 XML messages against Schematron business rules.

    Args:
        rulebook_or_path: Friendly preset name ('sepa', 'fednow', 'cbpr')
            or Path to a custom .sch file.
    """

    def __init__(self, rulebook_or_path: str | Path = "sepa") -> None:
        self.rulebook_name = (
            str(rulebook_or_path)
            if isinstance(rulebook_or_path, str)
            else rulebook_or_path.name
        )
        self.schema_path = resolve_rulebook_path(rulebook_or_path)
        self.schema: SchematronSchema = parse_schematron(self.schema_path)

    @traced("schematron.validate")
    def validate(
        self, xml_input: str | bytes | Path | Element
    ) -> SchematronValidationResult:
        """Validate an XML document against the loaded Schematron schema.

        Args:
            xml_input: XML string, raw bytes, file Path, or ElementTree Element.

        Returns:
            SchematronValidationResult with pass/fail verdict and violations.

        Raises:
            ValueError: If the input XML cannot be parsed.
        """
        start_time = time.perf_counter()

        root: Element
        if isinstance(xml_input, Element):
            root = xml_input
        elif isinstance(xml_input, Path):
            content = xml_input.read_text(encoding="utf-8")
            root = defused_et.fromstring(content)
        elif isinstance(xml_input, str):
            if xml_input.strip().startswith("<"):
                root = defused_et.fromstring(xml_input)
            else:
                path = validate_path(xml_input, must_exist=True)
                content = Path(path).read_text(encoding="utf-8")
                root = defused_et.fromstring(content)
        elif isinstance(xml_input, bytes):
            root = defused_et.fromstring(xml_input)
        else:
            raise ValueError(f"Unsupported XML input type: {type(xml_input)}")

        violations: list[SchematronViolation] = []
        rules_evaluated = 0

        for pattern in self.schema.patterns:
            for rule in pattern.rules:
                nodes = find_context_elements(
                    root, rule.context, self.schema.namespaces
                )
                for node in nodes:
                    for assertion in rule.assertions:
                        rules_evaluated += 1
                        violation = evaluate_assertion(
                            assertion,
                            node,
                            rule.context,
                            self.schema.namespaces,
                        )
                        if violation:
                            violations.append(violation)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        rules_passed = rules_evaluated - len(violations)
        is_valid = not any(v.severity == "ERROR" for v in violations)

        set_span_attributes(
            **{
                "schematron.rulebook": self.rulebook_name,
                "schematron.valid": is_valid,
                "schematron.rules_evaluated": rules_evaluated,
                "schematron.violations_count": len(violations),
            }
        )

        return SchematronValidationResult(
            is_valid=is_valid,
            rulebook=self.rulebook_name,
            violations=violations,
            rules_evaluated=rules_evaluated,
            rules_passed=max(0, rules_passed),
            duration_ms=round(duration_ms, 3),
        )


def validate_schematron(
    xml_input: str | bytes | Path | Element,
    rulebook: str | Path = "sepa",
) -> SchematronValidationResult:
    """Convenience function to validate an XML document against a Schematron rulebook.

    Args:
        xml_input: XML string, raw bytes, file Path, or ElementTree Element.
        rulebook: Friendly preset ('sepa', 'fednow', 'cbpr') or path to .sch file.

    Returns:
        SchematronValidationResult containing diagnostics and pass/fail verdict.
    """
    validator = SchematronValidator(rulebook)
    return validator.validate(xml_input)
