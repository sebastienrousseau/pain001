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

"""Bank and scheme overlays: the shared assertion grammar.

An overlay is a small rule set a bank or scheme layers on top of the
XSD: "the charge bearer must be SLEV for EUR", "the town is required",
"no proprietary service level". ``iso20022-bank-profile-mcp`` and the
readiness suite each carried an evaluator for the same three verbs;
this module is the one both can import, reads their files unchanged,
and adds the verbs the corpus needs.

Rule shape (a bank-profile ``custom_rules`` entry is exactly this)::

    rule_id: sepa-eur-slev
    description: For EUR payments the charge bearer must be SLEV.
    locator: ChrgBr
    assertion: if:Ccy=EUR:equals:SLEV
    error_code: SEPA_CHRGBR_NOT_SLEV      # optional
    severity: error                       # optional, default error

Locators
    A local name (``ChrgBr``) matches every element with that name; a
    slash path (``PmtInf/ChrgBr``, ``Cdtr/PstlAdr/TwnNm``) matches
    every element whose path ends with it. ``required`` asks for at
    least one match; every other verb is checked on each match.

Verbs
    ``required``, ``forbidden``, ``equals:<v>``, ``one_of:[a,b,c]``
    (or ``one_of:a|b|c``), ``max_length:<n>``, ``matches:<regex>``,
    ``charset:<name>`` (``iso20022``, ``ascii``, ``latin1``) and
    ``if:<elem>=<v>:<verb...>``, whose tail is any verb above; the
    original ``if:<elem>=<v>:equals:<v2>`` reads the same, and
    ``if:<elem>:<verb...>`` (no ``=``) applies the tail when the element
    is present at all.

Patches
    An overlay may carry a ``patch``: scenario keys deep-merged into the
    scenario before building, so a bank's fixed choices (a service level
    code, a charge bearer) produce their own file variant beside the
    generic one, judged by the overlay's rules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from defusedxml import ElementTree as defused_et

from pain001.validation.charset import find_invalid_characters

VERBS: tuple[str, ...] = (
    "required",
    "forbidden",
    "equals:",
    "one_of:",
    "max_length:",
    "matches:",
    "charset:",
    "if:",
)
CHARSETS: tuple[str, ...] = ("iso20022", "ascii", "latin1")
#: The source-of-truth directory in a checkout (absent from the wheel).
OVERLAYS_DIR = Path(__file__).resolve().parents[3] / "scenarios" / "overlays"


class OverlayError(ValueError):
    """An overlay file or rule is malformed; the message says where."""


@dataclass(frozen=True)
class Rule:
    """One assertion.

    Attributes:
        rule_id: Stable id, unique within the overlay.
        description: What the rule means, for findings.
        locator: A local name or a slash path suffix.
        assertion: The verb and its argument.
        error_code: Machine code for findings; defaults to the id.
        severity: ``error`` or ``warning``.
    """

    rule_id: str
    description: str
    locator: str
    assertion: str
    error_code: str = ""
    severity: str = "error"

    @property
    def code(self) -> str:
        """The error code, falling back to the rule id."""
        return self.error_code or self.rule_id


@dataclass(frozen=True)
class Overlay:
    """A named rule set with its citation.

    Attributes:
        overlay_id: Stable id, e.g. ``gb.boe.chaps-purpose``.
        title: Human title.
        applies_to: Scenario ids or families it targets; empty means all.
        source: Citation of the document it derives from.
        rules: The rules.
        path: Where it was loaded from, if a file.
        patch: Scenario keys merged in before building a variant.
        patches: Per-scenario additions to ``patch``, keyed by scenario id.
        versions: Message types the overlay covers; empty means every
            edition. A guideline written for pain.001.001.03 does not
            judge a .09 file, whose elements are spelled differently.
    """

    overlay_id: str
    title: str
    applies_to: tuple[str, ...] = ()
    source: dict[str, Any] = field(default_factory=dict)
    rules: tuple[Rule, ...] = ()
    path: Path | None = None
    patch: dict[str, Any] = field(default_factory=dict)
    patches: dict[str, dict[str, Any]] = field(default_factory=dict)
    versions: tuple[str, ...] = ()

    def patch_for(self, scenario_id: str) -> dict[str, Any]:
        """The patch for one scenario: ``patch`` plus its ``patches`` entry."""
        from pain001.corpus.builder import deep_merge  # noqa: PLC0415

        return deep_merge(self.patch, self.patches.get(scenario_id, {}))

    @property
    def has_patch(self) -> bool:
        """True when the overlay builds variants."""
        return bool(self.patch or self.patches)

    def applies(
        self,
        scenario_id: str,
        family: str | None = None,
        version: str | None = None,
    ) -> bool:
        """True when the overlay targets the scenario or its family.

        Args:
            scenario_id: The scenario.
            family: Its rail family.
            version: The edition being judged; ``None`` skips the check.

        Returns:
            Whether the overlay applies.
        """
        if (
            version is not None
            and self.versions
            and version not in self.versions
        ):
            return False
        if not self.applies_to:
            return True
        return scenario_id in self.applies_to or family in self.applies_to


@dataclass(frozen=True)
class Finding:
    """One violated rule at one element.

    Attributes:
        rule_id: The rule.
        code: Its error code.
        severity: ``error`` or ``warning``.
        locator: The rule's locator.
        path: The element path checked, or the locator when absent.
        assertion: The rule's assertion.
        message: The rule's description.
        value: The offending text, if any.
    """

    rule_id: str
    code: str
    severity: str
    locator: str
    path: str
    assertion: str
    message: str
    value: str | None = None


def assertion_is_known(assertion: str) -> bool:
    """True when the assertion starts with a verb this module evaluates."""
    return any(assertion.startswith(verb) for verb in VERBS)


def parse_rule(raw: dict[str, Any], where: str = "<rule>") -> Rule:
    """Build a :class:`Rule` from a mapping, checking the assertion.

    Args:
        raw: The mapping (bank-profile ``custom_rules`` entries qualify).
        where: A label for error messages.

    Returns:
        The rule.

    Raises:
        OverlayError: If a field is missing or the verb is unknown.
    """
    missing = [
        k
        for k in ("rule_id", "description", "locator", "assertion")
        if not raw.get(k)
    ]
    if missing:
        raise OverlayError(f"{where}: rule is missing {', '.join(missing)}")
    assertion = str(raw["assertion"])
    if not assertion_is_known(assertion):
        raise OverlayError(
            f"{where}: rule {raw['rule_id']!r} uses an unknown verb in "
            f"{assertion!r}; known verbs: {', '.join(VERBS)}"
        )
    _parse_assertion(assertion, f"{where}: rule {raw['rule_id']!r}")
    severity = str(raw.get("severity", "error"))
    if severity not in ("error", "warning"):
        raise OverlayError(
            f"{where}: rule {raw['rule_id']!r} severity must be error or warning"
        )
    return Rule(
        str(raw["rule_id"]),
        str(raw["description"]),
        str(raw["locator"]),
        assertion,
        str(raw.get("error_code", "")),
        severity,
    )


def overlay_from(
    document: dict[str, Any], path: Path | None = None
) -> Overlay:
    """Build an :class:`Overlay` from a parsed file.

    Both the corpus shape (``overlay_id``, ``rules``) and the bank-profile
    shape (``profile_id``, ``custom_rules``) are accepted.

    Args:
        document: The parsed YAML or JSON.
        path: Where it came from, for messages.

    Returns:
        The overlay.

    Raises:
        OverlayError: If the id is missing or a rule is malformed.
    """
    where = str(path) if path else "<overlay>"
    overlay_id = document.get("overlay_id") or document.get("profile_id")
    if not overlay_id:
        raise OverlayError(f"{where}: overlay_id (or profile_id) is required")
    raw_rules = document.get("rules", document.get("custom_rules", [])) or []
    rules = tuple(parse_rule(r, where) for r in raw_rules)
    ids = [r.rule_id for r in rules]
    if len(set(ids)) != len(ids):
        raise OverlayError(f"{where}: duplicate rule ids")
    applies = document.get("applies_to") or []
    if isinstance(applies, str):
        applies = [applies]
    return Overlay(
        str(overlay_id),
        str(
            document.get("title")
            or document.get("market_practice")
            or overlay_id
        ),
        tuple(str(a) for a in applies),
        dict(document.get("source") or {}),
        rules,
        path,
        dict(document.get("patch") or {}),
        {str(k): dict(v) for k, v in (document.get("patches") or {}).items()},
        tuple(str(v) for v in (document.get("versions") or [])),
    )


def load_overlay(path: str | Path) -> Overlay:
    """Load one YAML or JSON overlay file.

    Args:
        path: The file.

    Returns:
        The overlay.

    Raises:
        OverlayError: If the file does not parse or is malformed.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        document = (
            json.loads(text)
            if path.suffix == ".json"
            else yaml.safe_load(text)
        )
    except (ValueError, yaml.YAMLError) as exc:
        raise OverlayError(
            f"{path}: not valid {path.suffix[1:].upper()}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise OverlayError(f"{path}: expected a mapping at the top level")
    return overlay_from(document, path)


def load_overlays(root: str | Path = OVERLAYS_DIR) -> list[Overlay]:
    """Load every overlay under ``root``, sorted by id.

    Args:
        root: The overlays directory.

    Returns:
        The overlays; empty when the directory does not exist.
    """
    root = Path(root)
    files = sorted(
        p for p in root.rglob("*") if p.suffix in (".yaml", ".yml", ".json")
    )
    return sorted((load_overlay(p) for p in files), key=lambda o: o.overlay_id)


# --- evaluation --------------------------------------------------------------


def _local(tag: str) -> str:
    """The local name of a tag, namespace stripped."""
    return tag.rsplit("}", 1)[-1]


def _index(xml: str) -> list[tuple[str, Any]]:
    """Every element with its slash path, in document order."""
    root = defused_et.fromstring(xml)
    found: list[tuple[str, Any]] = []

    def visit(node: Any, parent: str) -> None:
        """Record ``node`` and its subtree with their paths."""
        path = f"{parent}/{_local(node.tag)}"
        found.append((path, node))
        for child in node:
            visit(child, path)

    visit(root, "")
    return found


def _matches(locator: str, path: str) -> bool:
    """True when ``path`` is what ``locator`` names."""
    if "/" in locator:
        return path == locator or path.endswith("/" + locator.strip("/"))
    return path.rsplit("/", 1)[-1] == locator


def _select(
    index: list[tuple[str, Any]], locator: str
) -> list[tuple[str, Any]]:
    """Every indexed element ``locator`` matches, in document order."""
    return [(p, n) for p, n in index if _matches(locator, p)]


def _text(node: Any) -> str | None:
    """The element's stripped text, or ``None`` when it has none."""
    return None if node.text is None else str(node.text).strip()


def _first_text(index: list[tuple[str, Any]], locator: str) -> str | None:
    """The first matching element's text, else the first attribute so named.

    ``if:Ccy=EUR`` reads the account currency element when there is one
    and the ``Ccy`` attribute of an amount otherwise, which is where the
    currency usually lives in pain.001.
    """
    for _, node in _select(index, locator):
        text = _text(node)
        if text is not None:
            return text
    if "/" not in locator:
        for _, node in index:
            for name, value in node.attrib.items():
                if _local(name) == locator:
                    return str(value).strip()
    return None


def _parse_assertion(assertion: str, where: str) -> tuple[str, Any]:
    """Split an assertion into ``(verb, argument)``, validating it."""
    if assertion in ("required", "forbidden"):
        return assertion, None
    verb, _, argument = assertion.partition(":")
    if verb == "equals":
        return verb, argument
    if verb == "one_of":
        inner = argument.strip()
        if inner.startswith("[") and inner.endswith("]"):
            inner = inner[1:-1]
        values = [v.strip() for v in re.split(r"[|,]", inner) if v.strip()]
        if not values:
            raise OverlayError(f"{where}: one_of needs at least one value")
        return verb, values
    if verb == "max_length":
        if not argument.isdigit():
            raise OverlayError(
                f"{where}: max_length needs a number, got {argument!r}"
            )
        return verb, int(argument)
    if verb == "matches":
        try:
            return verb, re.compile(argument)
        except re.error as exc:
            raise OverlayError(
                f"{where}: matches has a bad regex: {exc}"
            ) from exc
    if verb == "charset":
        if argument not in CHARSETS:
            raise OverlayError(
                f"{where}: charset must be one of {', '.join(CHARSETS)}"
            )
        return verb, argument
    if verb == "if":
        condition, _, tail = argument.partition(":")
        if not condition or not tail:
            raise OverlayError(
                f"{where}: if needs the form if:<elem>[=<value>]:<verb...>"
            )
        if tail.startswith("if:"):
            raise OverlayError(f"{where}: if cannot nest")
        parts = condition.split("=", 1)
        pair = (parts[0], parts[1] if len(parts) == 2 else None)
        return verb, (pair, _parse_assertion(tail, where))
    raise OverlayError(f"{where}: unknown verb in {assertion!r}")


def _charset_ok(text: str, name: str) -> bool:
    """True when every character of ``text`` is in the named set."""
    if name == "iso20022":
        return not find_invalid_characters(text)
    if name == "ascii":
        return text.isascii()
    return all(ord(ch) < 256 for ch in text)


def _violation(verb: str, argument: Any, text: str | None) -> bool:
    """True when a present element's text breaks a per-element verb."""
    if verb == "forbidden":
        return True
    if text is None:
        return verb != "max_length"
    if verb == "equals":
        return text != str(argument)
    if verb == "one_of":
        return text not in list(argument)
    if verb == "max_length":
        return len(text) > int(argument)
    if verb == "matches":
        return bool(argument.fullmatch(text) is None)
    return not _charset_ok(text, argument)  # charset


def evaluate_rules(rules: Any, xml: str) -> list[Finding]:
    """Check rules against one document.

    Args:
        rules: Rules to apply (an :class:`Overlay`'s or any iterable).
        xml: The document text.

    Returns:
        One :class:`Finding` per violated rule and element, in rule then
        document order.
    """
    index = _index(xml)
    findings: list[Finding] = []
    for rule in rules:
        verb, argument = _parse_assertion(rule.assertion, rule.rule_id)
        if verb == "if":
            (cond_elem, cond_value), (verb, argument) = argument
            if cond_value is None:
                if not _select(index, cond_elem):
                    continue
            elif _first_text(index, cond_elem) != cond_value:
                continue
        matches = _select(index, rule.locator)
        if verb == "required":
            if not any(_text(n) is not None for _, n in matches):
                findings.append(_finding(rule, rule.locator, None))
            continue
        for path, node in matches:
            text = _text(node)
            if _violation(verb, argument, text):
                findings.append(_finding(rule, path, text))
    return findings


def _finding(rule: Rule, path: str, value: str | None) -> Finding:
    """A :class:`Finding` for ``rule`` at ``path``."""
    return Finding(
        rule.rule_id,
        rule.code,
        rule.severity,
        rule.locator,
        path,
        rule.assertion,
        rule.description,
        value,
    )


def evaluate(overlay: Overlay, xml: str) -> list[Finding]:
    """Check an overlay against one document; see :func:`evaluate_rules`."""
    return evaluate_rules(overlay.rules, xml)


__all__ = [
    "CHARSETS",
    "OVERLAYS_DIR",
    "VERBS",
    "Finding",
    "Overlay",
    "OverlayError",
    "Rule",
    "assertion_is_known",
    "evaluate",
    "evaluate_rules",
    "load_overlay",
    "load_overlays",
    "overlay_from",
    "parse_rule",
]
