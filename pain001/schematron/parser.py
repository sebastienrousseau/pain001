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

"""Parser for ISO Schematron (ISO/IEC 19757-3) schema files."""

from dataclasses import dataclass, field
from pathlib import Path

from defusedxml import ElementTree as defused_et

SCHEMATRON_NS_ISO = "http://purl.oclc.org/dsdl/schematron"
SCHEMATRON_NS_15 = "http://www.ascc.net/xml/schematron"


@dataclass
class SchematronAssertion:
    """A single assert or report statement within a Schematron rule.

    Attributes:
        rule_id: Unique rule identifier (from id or rule attribute).
        test: The XPath test expression.
        message: Human-readable error/diagnostic message.
        is_report: True if this is a <report> (fails when test is true).
        severity: 'ERROR' or 'WARNING'.
    """

    rule_id: str
    test: str
    message: str
    is_report: bool = False
    severity: str = "ERROR"


@dataclass
class SchematronRule:
    """A rule element specifying context and containing assertions."""

    context: str
    assertions: list[SchematronAssertion] = field(default_factory=list)


@dataclass
class SchematronPattern:
    """A pattern element grouping related rules."""

    pattern_id: str
    title: str
    rules: list[SchematronRule] = field(default_factory=list)


@dataclass
class SchematronSchema:
    """Parsed representation of an entire Schematron document."""

    title: str
    namespaces: dict[str, str] = field(default_factory=dict)
    patterns: list[SchematronPattern] = field(default_factory=list)

    @property
    def total_assertions(self) -> int:
        """Count all assertions across all patterns and rules."""
        return sum(
            len(rule.assertions)
            for pattern in self.patterns
            for rule in pattern.rules
        )


def _strip_ns(tag: str) -> str:
    """Strip XML namespace prefix enclosed in braces from tag name."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def parse_schematron(source: str | bytes | Path) -> SchematronSchema:
    """Parse a Schematron (.sch) XML document into a SchematronSchema object.

    Args:
        source: XML string, bytes, or Path pointing to the .sch file.

    Returns:
        SchematronSchema representing parsed rules and namespaces.

    Raises:
        ValueError: If the source does not represent a valid Schematron document.
    """
    if isinstance(source, Path):
        content = source.read_text(encoding="utf-8")
        root = defused_et.fromstring(content)
    elif isinstance(source, str):
        if source.strip().startswith("<"):
            root = defused_et.fromstring(source)
        else:
            path = Path(source)
            content = path.read_text(encoding="utf-8")
            root = defused_et.fromstring(content)
    elif isinstance(source, bytes):
        root = defused_et.fromstring(source)
    else:
        raise ValueError(f"Unsupported Schematron source type: {type(source)}")

    root_tag = _strip_ns(root.tag)
    if root_tag != "schema":
        raise ValueError(f"Root element must be 'schema', got '{root.tag}'")

    title = ""
    namespaces: dict[str, str] = {}
    patterns: list[SchematronPattern] = []

    for child in root:
        tag = _strip_ns(child.tag)
        if tag == "title":
            title = (child.text or "").strip()
        elif tag == "ns":
            prefix = child.attrib.get("prefix", "").strip()
            uri = child.attrib.get("uri", "").strip()
            if prefix and uri:
                namespaces[prefix] = uri
        elif tag == "pattern":
            pat_id = child.attrib.get(
                "id", child.attrib.get("name", "pattern")
            )
            pat_title = ""
            pat_rules: list[SchematronRule] = []

            for p_child in child:
                p_tag = _strip_ns(p_child.tag)
                if p_tag == "title":
                    pat_title = (p_child.text or "").strip()
                elif p_tag == "rule":
                    context = p_child.attrib.get("context", ".").strip()
                    rule_assertions: list[SchematronAssertion] = []

                    for r_child in p_child:
                        r_tag = _strip_ns(r_child.tag)
                        if r_tag in ("assert", "report"):
                            test = r_child.attrib.get("test", "").strip()
                            rule_id = r_child.attrib.get(
                                "id",
                                r_child.attrib.get(
                                    "flag", f"RULE-{len(rule_assertions) + 1}"
                                ),
                            )
                            role = r_child.attrib.get("role", "error").lower()
                            severity = (
                                "WARNING"
                                if role in ("warn", "warning", "info")
                                else "ERROR"
                            )
                            msg = " ".join("".join(r_child.itertext()).split())

                            rule_assertions.append(
                                SchematronAssertion(
                                    rule_id=rule_id,
                                    test=test,
                                    message=msg
                                    or f"Assertion {rule_id} failed",
                                    is_report=(r_tag == "report"),
                                    severity=severity,
                                )
                            )

                    if rule_assertions:
                        pat_rules.append(
                            SchematronRule(
                                context=context,
                                assertions=rule_assertions,
                            )
                        )

            patterns.append(
                SchematronPattern(
                    pattern_id=pat_id,
                    title=pat_title,
                    rules=pat_rules,
                )
            )

    return SchematronSchema(
        title=title,
        namespaces=namespaces,
        patterns=patterns,
    )
