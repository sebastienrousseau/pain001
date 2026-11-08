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

import operator
from collections.abc import Callable
from typing import Any
from xml.etree.ElementTree import Element  # nosec B405

from pain001.schematron._xpath_syntax import (
    DELIMITERS,
    scan,
    split_top,
    step_parts,
)
from pain001.schematron.models import SchematronViolation
from pain001.schematron.parser import SchematronAssertion

#: The relational operators Schematron tests use, by token.
_COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


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


class NodeSet(list[Element]):
    """The elements a location path selected, in document order.

    XPath treats a node-set differently from a string: it is true when
    it is not empty, whatever the nodes contain, and ``=`` holds when
    any one of its nodes compares equal.
    """


def _filter(
    nodes: list[Element], predicate: str, namespaces: dict[str, str]
) -> list[Element]:
    """Keep the nodes a predicate selects: a position, or a test."""
    if predicate.strip().isdigit():
        position = int(predicate)
        return nodes[position - 1 : position] if position else []
    return [
        node
        for node in nodes
        if XPathEvaluator(node, namespaces).evaluate(predicate)
    ]


def _child_step(
    nodes: list[Element], step: str, namespaces: dict[str, str]
) -> list[Element]:
    """Apply one child step, predicates included, to every node."""
    name, predicates = step_parts(step)
    selected = [
        child
        for node in nodes
        for child in node
        if _match_tag(child, name, namespaces)
    ]
    for predicate in predicates:
        selected = _filter(selected, predicate, namespaces)
    return selected


def select_path(
    node: Element, path: str, namespaces: dict[str, str]
) -> NodeSet | str | None:
    """Select a relative location path from a node.

    Args:
        node: The context node.
        path: Child steps separated by ``/``, each optionally with
            ``[...]`` predicates, or ending in an ``@attribute`` step.
        namespaces: Prefix-to-URI mapping for the name tests.

    Returns:
        The selected elements, or for an attribute step the first
        selected element's value of it (None when none has it).
    """
    nodes: list[Element] = [node]
    for step in split_top(path, "/"):
        if step.startswith("@"):
            return next(
                (n.attrib[step[1:]] for n in nodes if step[1:] in n.attrib),
                None,
            )
        if step != ".":
            nodes = _child_step(nodes, step, namespaces)
    return NodeSet(nodes)


def _string(value: Any) -> Any:
    """A node-set as its first node's text (None when empty); else as-is."""
    if isinstance(value, NodeSet):
        return (value[0].text or "").strip() if value else None
    return value


def _atoms(value: Any) -> list[Any]:
    """The values a comparison tries: each node's text, or the value."""
    if isinstance(value, NodeSet):
        return [(node.text or "").strip() for node in value]
    return [value]


def resolve_xpath_value(
    node: Element, path: str, namespaces: dict[str, str]
) -> Any:
    """Resolve a relative XPath expression on an element node.

    Returns the first selected element's text, an attribute's value,
    or None when nothing is selected.
    """
    return _string(select_path(node, path, namespaces))


def _read_token(expr: str, start: int) -> tuple[str, int]:
    """The token at ``start`` (not whitespace) and the index after it."""
    pair = expr[start : start + 2]
    if pair in ("<=", ">=", "!="):
        return pair, start + 2
    char = expr[start]
    if char in "(),=<>":
        return char, start + 1
    if char in "'\"":
        # A string literal, always given back in single quotes.
        close = expr.find(char, start + 1)
        close = len(expr) if close < 0 else close
        return f"'{expr[start + 1 : close]}'", close + 1
    # Word, number, function or path, predicates included; at least one
    # character, so a stray delimiter cannot stall the tokenizer.
    end = next(
        (
            index
            for index, found, level in scan(expr, start)
            if index > start
            and level == 0
            and (found.isspace() or found in DELIMITERS)
        ),
        len(expr),
    )
    return expr[start:end], end


def _tokenize(expr: str) -> list[str]:
    """Tokenize a Schematron XPath assertion expression."""
    tokens: list[str] = []
    index = 0
    while index < len(expr):
        if expr[index].isspace():
            index += 1
            continue
        token, index = _read_token(expr, index)
        tokens.append(token)
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
        """Apply comparison operator to left and right operands.

        A node-set side holds when any of its nodes does, so an empty one
        never does. Numbers compare numerically; anything else compares
        as strings, with ``None`` as the empty string. An unknown
        operator is false.
        """
        compare = _COMPARATORS.get(op)
        if compare is None:
            return False
        return any(
            _compare(compare, one, other)
            for one in _atoms(left)
            for other in _atoms(right)
        )

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

        return self._literal_or_path(tok), idx + 1

    def _literal_or_path(self, tok: str) -> Any:
        """A string or number literal, else a location path's value."""
        if tok.startswith("'") and tok.endswith("'"):
            return tok[1:-1]
        try:
            return float(tok) if "." in tok else int(tok)
        except ValueError:
            # A location path: a node-set, or an attribute's value.
            return select_path(self.node, tok, self.namespaces)

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

        function = _FUNCTIONS.get(fn_name)
        return (function(args) if function else None), idx


def _compare(
    compare: Callable[[Any, Any], bool], left: Any, right: Any
) -> bool:
    """Compare two atomic values, as numbers when both are numeric."""
    try:
        return bool(compare(float(left), float(right)))
    except (ValueError, TypeError):
        # Either side is not a number: compare them as strings.
        left_str = str(left) if left is not None else ""
        right_str = str(right) if right is not None else ""
        return bool(compare(left_str, right_str))


def _text_arg(args: list[Any], position: int) -> str:
    """Argument ``position`` as a string, ``""`` when missing or empty."""
    value = _string(args[position]) if len(args) > position else None
    return str(value) if value is not None else ""


def _number(args: list[Any]) -> float:
    """XPath ``number()``, with 0 for anything that is not a number."""
    try:
        return float(_string(args[0]) if args else 0)
    except (ValueError, TypeError):
        return 0.0


def _count(args: list[Any]) -> int:
    """XPath ``count()``: the nodes in a node-set, else 1 for a value."""
    arg = args[0] if args else None
    if isinstance(arg, NodeSet):
        return len(arg)
    return 1 if arg is not None and arg != "" else 0


#: The XPath functions assertions may call, by lower-case name.
_FUNCTIONS: dict[str, Callable[[list[Any]], Any]] = {
    "true": lambda args: True,
    "false": lambda args: False,
    "not": lambda args: not (args and args[0]),
    "boolean": lambda args: bool(args and args[0]),
    "number": _number,
    "string-length": lambda args: len(_text_arg(args, 0)),
    "starts-with": lambda args: _text_arg(args, 0).startswith(
        _text_arg(args, 1)
    ),
    "contains": lambda args: _text_arg(args, 1) in _text_arg(args, 0),
    "count": _count,
}


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
