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

"""The sandboxed Jinja environment the XML templates compile in.

:func:`compile_template` compiles a template's text once.
:func:`indent` is Jinja's ``indent`` filter on plain strings.

The templates indent every rendered macro (an address, a party, an
account) with ``| indent``. Under autoescape a macro's output is
:class:`markupsafe.Markup`, so Jinja's filter splits, joins and
concatenates ``Markup`` objects, and each step goes through MarkupSafe:
about half the render time of a 1,000-row pain.001.001.09 batch. Jinja
wraps the indent and the newline in ``Markup`` without escaping them, so
nothing is ever escaped there; the same steps on ``str`` give the same
text, which is wrapped back in ``Markup`` when the input was ``Markup``.
:func:`indent` is that, with Jinja's signature and behaviour.
"""

from __future__ import annotations

import functools
import re

from jinja2 import Template, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup


def indent(
    s: str, width: int | str = 4, first: bool = False, blank: bool = False
) -> str:
    """Indent every line but the first, as Jinja's ``indent`` does.

    Args:
        s: The text; ``Markup`` stays ``Markup``.
        width: Spaces to indent by, or the indent itself.
        first: Indent the first line too.
        blank: Indent empty lines too.

    Returns:
        The indented text, of the input's type.
    """
    indent_text = width if isinstance(width, str) else " " * width
    text = str(s) + "\n"
    if blank:
        rv = ("\n" + indent_text).join(text.splitlines())
    else:
        lines = text.splitlines()
        rv = lines.pop(0)
        if lines:
            rv += "\n" + "\n".join(
                indent_text + line if line else line for line in lines
            )
    if first:
        rv = indent_text + rv
    if isinstance(s, Markup):
        # rv is s, which was already Markup (escaped), plus the template's
        # own indent: nothing untrusted is marked safe here, as in Jinja's
        # do_indent, which wraps the indent in Markup the same way.
        return Markup(rv)  # nosec B704
    return rv


#: The XSD pattern of an IBAN element (IBAN2007Identifier).
_IBAN_SHAPE = re.compile(r"[A-Z]{2}[0-9]{2}[a-zA-Z0-9]{1,30}")


def is_iban(value: object) -> bool:
    """The templates' ``is iban`` test: an IBAN the ``<IBAN>`` element takes.

    True only for text in the XSD's IBAN shape (no spaces) whose check
    digits pass mod-97, so anything else stays an ``<Othr><Id>`` account
    number, as before 0.0.82 (ADR-0011).

    Args:
        value: The account value a template renders.

    Returns:
        Whether the value is written as ``<IBAN>``.
    """
    from pain001.validation.iban_validator import validate_iban_safe

    return (
        isinstance(value, str)
        and _IBAN_SHAPE.fullmatch(value) is not None
        and validate_iban_safe(value)
    )


@functools.lru_cache(maxsize=32)
def compile_template(template_source: str) -> Template:
    """Compile a template's text once, in the XML-autoescaping sandbox.

    Compiling cost about 8.6 ms of a 9 ms small-batch generation. The
    cache is keyed on the text itself, which the caller reads through
    the trusted-path check on every call, so an edited template is
    compiled again. A compiled Jinja template renders safely from
    several threads.

    Args:
        template_source: The template's text.

    Returns:
        The compiled template.
    """
    env = SandboxedEnvironment(
        autoescape=select_autoescape(
            enabled_extensions=("xml",),
            default_for_string=True,
        ),
    )
    # Same output as Jinja's indent, without MarkupSafe on every step.
    env.filters["indent"] = indent
    env.tests["iban"] = is_iban
    return env.from_string(template_source)


__all__ = ["compile_template", "indent", "is_iban"]
