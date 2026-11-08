# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The string ``indent`` filter gives exactly Jinja's output."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from jinja2.filters import do_indent
from markupsafe import Markup

from pain001.xml import generate_xml as gx
from pain001.xml._jinja import indent

TEXT = st.text(
    alphabet=st.sampled_from(list("ab<&>\"' \t\n\r\x0b\x0c\x1c ")),
    max_size=40,
)
WIDTH = st.one_of(
    st.integers(min_value=0, max_value=6),
    st.text(alphabet=st.sampled_from(list(" \t<&")), max_size=4),
)


@given(text=TEXT, width=WIDTH, first=st.booleans(), blank=st.booleans())
def test_plain_text_matches_jinja(
    text: str, width: int | str, first: bool, blank: bool
) -> None:
    expected = do_indent(text, width, first, blank)
    got = indent(text, width, first, blank)
    assert got == expected
    assert type(got) is type(expected)


@given(text=TEXT, width=WIDTH, first=st.booleans(), blank=st.booleans())
def test_markup_matches_jinja(
    text: str, width: int | str, first: bool, blank: bool
) -> None:
    markup = Markup(text)
    expected = do_indent(markup, width, first, blank)
    got = indent(markup, width, first, blank)
    assert got == expected
    assert isinstance(got, Markup)


def test_the_defaults_match_jinja() -> None:
    assert indent("a\nb") == do_indent("a\nb") == "a\n    b"


def test_compiled_templates_use_it() -> None:
    gx._compile_template.cache_clear()
    template = gx._compile_template("{{ x | indent('\t') }}")
    assert template.environment.filters["indent"] is indent
    assert template.render(x="a\n<b>") == "a\n\t&lt;b&gt;"
