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
from typing import Any

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


def _load_root(source: str | bytes | Path) -> Any:
    """Parse ``source``: XML text or bytes, or a path to read it from."""
    if isinstance(source, Path):
        return defused_et.fromstring(source.read_text(encoding="utf-8"))
    if isinstance(source, str):
        if source.strip().startswith("<"):
            return defused_et.fromstring(source)
        return defused_et.fromstring(Path(source).read_text(encoding="utf-8"))
    if isinstance(source, bytes):
        return defused_et.fromstring(source)
    raise ValueError(f"Unsupported Schematron source type: {type(source)}")


def _parse_assertion(
    element: Any, tag: str, number: int
) -> SchematronAssertion:
    """One ``<assert>`` or ``<report>``; ``number`` names it if unnamed."""
    test = element.attrib.get("test", "").strip()
    rule_id = element.attrib.get(
        "id", element.attrib.get("flag", f"RULE-{number}")
    )
    role = element.attrib.get("role", "error").lower()
    severity = "WARNING" if role in ("warn", "warning", "info") else "ERROR"
    msg = " ".join("".join(element.itertext()).split())
    return SchematronAssertion(
        rule_id=rule_id,
        test=test,
        message=msg or f"Assertion {rule_id} failed",
        is_report=(tag == "report"),
        severity=severity,
    )


def _parse_rule(element: Any) -> SchematronRule | None:
    """One ``<rule>`` with its assertions; ``None`` when it has none."""
    context = element.attrib.get("context", ".").strip()
    assertions: list[SchematronAssertion] = []
    for child in element:
        tag = _strip_ns(child.tag)
        if tag in ("assert", "report"):
            assertions.append(
                _parse_assertion(child, tag, len(assertions) + 1)
            )
    if not assertions:
        return None
    return SchematronRule(context=context, assertions=assertions)


def _parse_pattern(element: Any) -> SchematronPattern:
    """One ``<pattern>``: its title and the rules that assert something."""
    pat_id = element.attrib.get("id", element.attrib.get("name", "pattern"))
    title = ""
    rules: list[SchematronRule] = []
    for child in element:
        tag = _strip_ns(child.tag)
        if tag == "title":
            title = (child.text or "").strip()
        elif tag == "rule":
            rule = _parse_rule(child)
            if rule is not None:
                rules.append(rule)
    return SchematronPattern(pattern_id=pat_id, title=title, rules=rules)


def parse_schematron(source: str | bytes | Path) -> SchematronSchema:
    """Parse a Schematron (.sch) XML document into a SchematronSchema object.

    Args:
        source: XML string, bytes, or Path pointing to the .sch file.

    Returns:
        SchematronSchema representing parsed rules and namespaces.

    Raises:
        ValueError: If the source does not represent a valid Schematron document.
    """
    root = _load_root(source)
    root_tag = _strip_ns(root.tag)
    if root_tag != "schema":
        raise ValueError(f"Root element must be 'schema', got '{root.tag}'")

    schema = SchematronSchema(title="")
    for child in root:
        tag = _strip_ns(child.tag)
        if tag == "title":
            schema.title = (child.text or "").strip()
        elif tag == "ns":
            prefix = child.attrib.get("prefix", "").strip()
            uri = child.attrib.get("uri", "").strip()
            if prefix and uri:
                schema.namespaces[prefix] = uri
        elif tag == "pattern":
            schema.patterns.append(_parse_pattern(child))
    return schema
