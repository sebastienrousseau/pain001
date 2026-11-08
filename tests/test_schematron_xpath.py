# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The Schematron evaluator treats a location path as a node-set.

Until 0.0.82 a path evaluated to its first element's text: an element
with only children read as false, ``=`` saw only the first match, and
``[...]`` predicates were not understood. A rule that has to say "every
transaction" (EPC-PMT-002, EPC-PMT-003) needs all three, as XPath
defines them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 - parses literals below

import pytest

from pain001.schematron._xpath_syntax import scan, split_top, step_parts
from pain001.schematron.evaluator import (
    NodeSet,
    XPathEvaluator,
    _tokenize,
    resolve_xpath_value,
    select_path,
)

_BATCH = ET.fromstring(
    "<PmtInf>"
    "<ChrgBr>SLEV</ChrgBr>"
    '<Tx id="a"><ChrgBr>SLEV</ChrgBr><Amt>1</Amt></Tx>'
    '<Tx id="b"><ChrgBr>SHAR</ChrgBr><Amt>2</Amt></Tx>'
    '<Tx id="c"><Amt>3</Amt><Rmt>x]y</Rmt></Tx>'
    "</PmtInf>"
)


def _true(expr: str) -> bool:
    return XPathEvaluator(_BATCH, {}).evaluate(expr)


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        # An element with only children exists.
        ("Tx", True),
        ("boolean(Tx)", True),
        ("not(Missing)", True),
        # = holds when any node matches; an empty node-set never does.
        ("Tx/ChrgBr = 'SHAR'", True),
        ("Tx/ChrgBr = 'DEBT'", False),
        ("Missing = ''", False),
        ("Missing != 'x'", False),
        ("Tx/Amt > 2", True),
        # Predicates filter, and nest.
        ("Tx[ChrgBr = 'SHAR']", True),
        ("Tx[ChrgBr = 'DEBT']", False),
        ("not(Tx[not(ChrgBr)])", False),
        ("not(Tx[not(Amt)])", True),
        ("Tx[Amt = 1][ChrgBr = 'SLEV']", True),
        ("Tx[Amt = 1][ChrgBr = 'SHAR']", False),
        ("Tx[not(ChrgBr[. = 'SHAR'])]/Amt = 3", True),
        # A quoted bracket inside a predicate is not a bracket.
        ("Tx[Rmt = 'x]y']/Amt = 3", True),
        # Positions.
        ("Tx[2]/ChrgBr = 'SHAR'", True),
        ("Tx[2]/ChrgBr = 'SLEV'", False),
        ("Tx[0]", False),
        ("Tx[9]", False),
        # count() counts.
        ("count(Tx) = 3", True),
        ("count(Tx[ChrgBr]) = 2", True),
        ("count(Missing) = 0", True),
        ("count('x') = 1", True),
        ("count('') = 0", True),
        ("count() = 0", True),
        # Functions read a node-set as its first node's text.
        ("string-length(Tx/ChrgBr) = 4", True),
        ("starts-with(Tx/ChrgBr, 'SL')", True),
        ("contains(Tx/ChrgBr, 'LE')", True),
        ("number(Tx/Amt) = 1", True),
        ("number(Missing) = 0", True),
        ("string-length(Missing) = 0", True),
        # Attributes after a predicate.
        ("Tx[ChrgBr = 'SHAR']/@id = 'b'", True),
        ("Tx/@missing", False),
        # The current node.
        ("./ChrgBr = 'SLEV'", True),
    ],
)
def test_node_set_semantics(expr: str, expected: bool) -> None:
    assert _true(expr) is expected


def test_select_path_returns_every_match_in_order() -> None:
    selected = select_path(_BATCH, "Tx", {})
    assert isinstance(selected, NodeSet)
    assert [tx.get("id") for tx in selected] == ["a", "b", "c"]
    assert select_path(_BATCH, "Tx[ChrgBr]/@id", {}) == "a"
    assert select_path(_BATCH, ".", {}) == [_BATCH]


def test_resolve_xpath_value_keeps_its_contract() -> None:
    assert resolve_xpath_value(_BATCH, "Tx/ChrgBr", {}) == "SLEV"
    assert resolve_xpath_value(_BATCH, "Tx[2]/ChrgBr", {}) == "SHAR"
    assert resolve_xpath_value(_BATCH, "Missing", {}) is None
    assert resolve_xpath_value(_BATCH, "Tx/@id", {}) == "a"


def test_a_predicate_stays_in_one_token() -> None:
    assert _tokenize("not(Tx[not(ChrgBr = 'SLEV')]) and Tx[1]") == [
        "not",
        "(",
        "Tx[not(ChrgBr = 'SLEV')]",
        ")",
        "and",
        "Tx[1]",
    ]


@pytest.mark.parametrize(
    ("expr", "tokens"),
    [
        ("a ! b", ["a", "!", "b"]),
        ("a!=b", ["a", "!=", "b"]),
        ("'open", ["'open'"]),
        ("\"x\" = 'y'", ["'x'", "=", "'y'"]),
        ("f(a,b)>=1", ["f", "(", "a", ",", "b", ")", ">=", "1"]),
    ],
)
def test_tokens(expr: str, tokens: list[str]) -> None:
    """A lone ``!`` is a token of its own: it used to stall the loop."""
    assert _tokenize(expr) == tokens


def test_paths_split_only_at_top_level() -> None:
    assert split_top("a/b[c/d = '/']/e", "/") == ["a", "b[c/d = '/']", "e"]
    assert split_top("//a/", "/") == ["a"]
    assert step_parts("b[c][d[e]]") == ("b", ["c", "d[e]"])
    assert step_parts("b[x = ']']") == ("b", ["x = ']'"])
    assert step_parts("b") == ("b", [])


def test_scan_reports_the_nesting_level() -> None:
    levels = [level for _, _, level in scan("a[b'c]'][d]e")]
    #        a  [  b  '  c  ]  '  ]  [  d  ]  e
    assert levels == [0, 0, 1, 1, 2, 2, 2, 0, 0, 1, 0, 0]
    assert [level for _, _, level in scan("a'b'")] == [0, 0, 0, 0]
