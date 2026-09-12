# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Importing the library must not load the CLI, lxml or sqlite3."""

from __future__ import annotations

import subprocess
import sys

import pytest

import pain001


def test_main_resolves_lazily_and_unknown_names_do_not() -> None:
    from pain001.__main__ import main as entry

    assert pain001.main is entry
    with pytest.raises(AttributeError, match="no attribute 'nope'"):
        _ = pain001.nope


def test_import_does_not_load_optional_modules() -> None:
    """A fresh interpreter, so this test's own imports cannot mask the result.

    lxml is blocked outright: xmlschema imports it opportunistically when
    it is installed, which is not the library pulling it in. The library's
    own modules must import cleanly without it, and rich and sqlite3 must
    never be loaded on import.
    """
    code = (
        "import sys\n"
        "sys.modules['lxml'] = None\n"
        "sys.modules['lxml.etree'] = None\n"
        "import pain001, pain001.twins, pain001.corpus\n"
        "from pain001.xml.generate_xml import generate_xml_string\n"
        "from pain001.validation.schema_validator import SchemaValidator\n"
        "print(sorted(m for m in ('rich', 'sqlite3', 'pygments') if m in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "[]", out.stdout
