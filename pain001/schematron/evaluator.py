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

"""XPath expression evaluator for Schematron assertions in ISO 20022 messages."""

from typing import Any
from xml.etree.ElementTree import Element  # nosec B405

from pain001.schematron.models import SchematronViolation
from pain001.schematron.parser import SchematronAssertion


def _local_tag(tag: str) -> str:
    """Return the local tag name without XML namespace."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _match_tag(
    element: Element, target_step: str, namespaces: dict[str, str]
) -> bool:
    """Check if an element matches an XPath tag step."""
    if target_step == "*":
        return True

    target_local = target_step
    target_ns = None

    if ":" in target_step:
        prefix, target_local = target_step.split(":", 1)
        target_ns = namespaces.get(prefix)

    elem_tag = element.tag
    if elem_tag.startswith("{"):
        elem_ns, elem_local = elem_tag[1:].split("}", 1)
        if target_ns:
            return elem_local == target_local and elem_ns == target_ns
        return elem_local == target_local
    return elem_tag == target_local


def find_context_elements(
    root: Element, context_expr: str, namespaces: dict[str, str]
) -> list[Element]:
    """Find all elements in the XML document matching a Schematron rule context.

    Args:
        root: The XML root element.
        context_expr: Context XPath expression (e.g. '//pain:CdtTrfTxInf', 'pain:PmtInf').
        namespaces: Mapping of namespace prefixes to URIs.

    Returns:
        List of matching Element instances.
    """
    expr = context_expr.strip()
    if expr == "." or expr == "/":
        return [root]

    # Normalize double slashes
    is_descendant = expr.startswith("//")
    clean_expr = expr.lstrip("/")
    steps = [s.strip() for s in clean_expr.split("/") if s.strip()]

    if not steps:
        return [root]

    if is_descendant:
        # Match elements anywhere in the tree where the trailing steps match
        target_step = steps[-1]
        results: list[Element] = []
        for elem in root.iter():
            if _match_tag(elem, target_step, namespaces):
                results.append(elem)
        return results

    # Path from root
    current = [root]
    start_idx = 0
    if _match_tag(root, steps[0], namespaces):
        start_idx = 1

    for step in steps[start_idx:]:
        next_level: list[Element] = []
        for parent in current:
            for child in parent:
                if _match_tag(child, step, namespaces):
                    next_level.append(child)
        current = next_level

    return current


def resolve_xpath_value(
    node: Element, path: str, namespaces: dict[str, str]
) -> Any:
    """Resolve a relative XPath expression on an element node.

    Returns string value, number, list of elements, or None.
    """
    clean_path = path.strip()
    if not clean_path or clean_path == ".":
        return (node.text or "").strip()

    steps = [s.strip() for s in clean_path.split("/") if s.strip()]
    current_elements = [node]

    for step in steps:
        if step.startswith("@"):
            attr_name = step[1:]
            for elem in current_elements:
                if attr_name in elem.attrib:
                    return elem.attrib[attr_name]
            return None

        next_elems: list[Element] = []
        for elem in current_elements:
            for child in elem:
                if _match_tag(child, step, namespaces):
                    next_elems.append(child)
        current_elements = next_elems
        if not current_elements:
            return None

    first = current_elements[0]
    return (first.text or "").strip()


def _tokenize(expr: str) -> list[str]:
    """Tokenize a Schematron XPath assertion expression."""
    tokens: list[str] = []
    i = 0
    n = len(expr)

    while i < n:
        c = expr[i]
        if c.isspace():
            i += 1
            continue

        if c in ("(", ")", ","):
            tokens.append(c)
            i += 1
            continue

        # String literals with single or double quotes
        if c in ("'", '"'):
            quote = c
            start = i + 1
            i += 1
            while i < n and expr[i] != quote:
                i += 1
            tokens.append(f"'{expr[start:i]}'")
            i += 1
            continue

        # Multi-character comparison operators
        if expr[i : i + 2] in ("<=", ">=", "!="):
            tokens.append(expr[i : i + 2])
            i += 2
            continue

        if c in ("=", "<", ">"):
            tokens.append(c)
            i += 1
            continue

        # Word, number, function, or path
        start = i
        while (
            i < n
            and not expr[i].isspace()
            and expr[i] not in ("(", ")", ",", "=", "<", ">", "!", "'", '"')
        ):
            i += 1
        tokens.append(expr[start:i])

    return tokens


class XPathEvaluator:
    """Recursive descent evaluator for Schematron XPath assertion expressions."""

    def __init__(self, node: Element, namespaces: dict[str, str]) -> None:
        self.node = node
        self.namespaces = namespaces

    def evaluate(self, expr_str: str) -> bool:
        """Evaluate an expression string against the node, returning a boolean."""
        tokens = _tokenize(expr_str)
        if not tokens:
            return True
        val, _ = self._eval_or(tokens, 0)
        return bool(val)

    def _eval_or(self, tokens: list[str], idx: int) -> tuple[Any, int]:
        """Evaluate 'or' logical expressions."""
        left, idx = self._eval_and(tokens, idx)
        while idx < len(tokens) and tokens[idx] == "or":
            right, idx = self._eval_and(tokens, idx + 1)
            left = bool(left) or bool(right)
        return left, idx

    def _eval_and(self, tokens: list[str], idx: int) -> tuple[Any, int]:
        """Evaluate 'and' logical expressions."""
        left, idx = self._eval_comparison(tokens, idx)
        while idx < len(tokens) and tokens[idx] == "and":
            right, idx = self._eval_comparison(tokens, idx + 1)
            left = bool(left) and bool(right)
        return left, idx

    def _eval_comparison(self, tokens: list[str], idx: int) -> tuple[Any, int]:
        """Evaluate relational comparison operations."""
        left, idx = self._eval_primary(tokens, idx)
        if idx < len(tokens) and tokens[idx] in (
            "=",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
        ):
            op = tokens[idx]
            right, idx = self._eval_primary(tokens, idx + 1)
            left = self._apply_comparison(left, op, right)
        return left, idx

    def _apply_comparison(self, left: Any, op: str, right: Any) -> bool:
        """Apply comparison operator to left and right operands."""
        # String comparison
        left_str = str(left) if left is not None else ""
        right_str = str(right) if right is not None else ""

        # Check numeric comparison
        try:
            left_num = float(left)
            right_num = float(right)
            if op == "=":
                return left_num == right_num
            if op == "!=":
                return left_num != right_num
            if op == "<":
                return left_num < right_num
            if op == "<=":
                return left_num <= right_num
            if op == ">":
                return left_num > right_num
            if op == ">=":
                return left_num >= right_num
        except (ValueError, TypeError):
            pass

        if op == "=":
            return left_str == right_str
        if op == "!=":
            return left_str != right_str
        if op == "<":
            return left_str < right_str
        if op == "<=":
            return left_str <= right_str
        if op == ">":
            return left_str > right_str
        if op == ">=":
            return left_str >= right_str
        return False

    def _eval_primary(self, tokens: list[str], idx: int) -> tuple[Any, int]:
        """Evaluate primary token, literal, subexpression, or function call."""
        if idx >= len(tokens):
            return None, idx

        tok = tokens[idx]

        if tok == "(":
            val, idx = self._eval_or(tokens, idx + 1)
            if idx < len(tokens) and tokens[idx] == ")":
                idx += 1
            return val, idx

        # Function calls
        if idx + 1 < len(tokens) and tokens[idx + 1] == "(":
            fn_name = tok.lower()
            return self._eval_function(fn_name, tokens, idx + 2)

        # String literal
        if tok.startswith("'") and tok.endswith("'"):
            return tok[1:-1], idx + 1

        # Number literal
        try:
            if "." in tok:
                return float(tok), idx + 1
            return int(tok), idx + 1
        except ValueError:
            pass

        # XPath node / attribute resolution
        val = resolve_xpath_value(self.node, tok, self.namespaces)
        return val, idx + 1

    def _eval_function(
        self, fn_name: str, tokens: list[str], idx: int
    ) -> tuple[Any, int]:
        """Evaluate XPath function call by name and argument list."""
        args: list[Any] = []
        if idx < len(tokens) and tokens[idx] == ")":
            idx += 1
        else:
            while idx < len(tokens):
                arg_val, idx = self._eval_or(tokens, idx)
                args.append(arg_val)
                if idx < len(tokens) and tokens[idx] == ",":
                    idx += 1
                    continue
                if idx < len(tokens) and tokens[idx] == ")":
                    idx += 1
                break

        if fn_name == "true":
            return True, idx

        if fn_name == "false":
            return False, idx

        if fn_name == "not":
            arg = args[0] if args else None
            return (not bool(arg)), idx

        if fn_name == "boolean":
            arg = args[0] if args else None
            return bool(arg), idx

        if fn_name == "number":
            arg = args[0] if args else 0
            try:
                return float(arg), idx
            except (ValueError, TypeError):
                return 0.0, idx

        if fn_name == "string-length":
            arg = str(args[0]) if args and args[0] is not None else ""
            return len(arg), idx

        if fn_name == "starts-with":
            s = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            prefix = (
                str(args[1]) if len(args) > 1 and args[1] is not None else ""
            )
            return s.startswith(prefix), idx

        if fn_name == "contains":
            s = str(args[0]) if len(args) > 0 and args[0] is not None else ""
            sub = str(args[1]) if len(args) > 1 and args[1] is not None else ""
            return sub in s, idx

        if fn_name == "count":
            arg = args[0] if args else None
            return (1 if arg is not None and arg != "" else 0), idx

        return None, idx


def evaluate_assertion(
    assertion: SchematronAssertion,
    node: Element,
    context_path: str,
    namespaces: dict[str, str],
) -> SchematronViolation | None:
    """Evaluate a single Schematron assertion against an XML node.

    Returns a SchematronViolation if the assertion fails, or None if it passes.
    """
    evaluator = XPathEvaluator(node, namespaces)
    result = evaluator.evaluate(assertion.test)

    # For <assert>, condition must be True.
    # For <report>, condition being True indicates an error.
    failed = not result if not assertion.is_report else result

    if failed:
        line_num = getattr(node, "sourceline", None)
        return SchematronViolation(
            rule_id=assertion.rule_id,
            message=assertion.message,
            context=context_path,
            test=assertion.test,
            line_number=line_num,
            severity=assertion.severity,
        )
    return None
