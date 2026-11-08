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


#: Modules ``pain001 --help`` must not execute. Together they cost about
#: 170 ms of the 0.0.81 start-up (261 ms measured for the plan, 320 ms
#: here with pyarrow installed); --help now takes about 120 ms.
_HEAVY_AT_STARTUP = (
    "elementpath",  # what xmlschema imports first when it actually loads
    "pyarrow",
    "pain001.twins.iso_json",
    "pain001.async_adapter",
)


def test_cli_help_does_not_load_heavy_modules() -> None:
    """``pain001 --help`` registers xmlschema lazily and never runs it."""
    code = (
        "import sys\n"
        "from pain001.__main__ import cli\n"
        "try:\n"
        "    cli(['--help'], prog_name='pain001')\n"
        "except SystemExit:\n"
        "    pass\n"
        f"heavy = {_HEAVY_AT_STARTUP!r}\n"
        "loaded = [m for m in heavy if m in sys.modules]\n"
        "xs = sys.modules.get('xmlschema')\n"
        "lazy = xs is None or type(xs).__name__ == '_LazyModule'\n"
        "print(loaded, lazy, file=sys.stderr)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stderr.strip().splitlines()[-1] == "[] True", out.stderr


def test_lazy_module_loads_on_first_use() -> None:
    """The lazily registered xmlschema works once touched."""
    code = (
        "import sys\n"
        "from pain001._lazy import lazy_module\n"
        "m = lazy_module('json')\n"
        "assert m is sys.modules['json']\n"
        "import pain001.xml.validate_via_xsd as v\n"
        "schema = v.xmlschema.XMLSchema\n"
        "print(type(sys.modules['xmlschema']).__name__)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "module"


def test_lazy_module_refuses_a_missing_module() -> None:
    from pain001._lazy import lazy_module

    with pytest.raises(ModuleNotFoundError, match="no_such_module_xyz"):
        lazy_module("no_such_module_xyz")


def test_lazy_module_registers_a_new_module_once() -> None:
    from pain001._lazy import lazy_module

    sys.modules.pop("calendar", None)
    first = lazy_module("calendar")
    assert sys.modules["calendar"] is first
    assert lazy_module("calendar") is first
    assert first.isleap(2024) is True


def test_every_public_name_resolves_and_is_listed() -> None:
    for name in pain001.__all__:
        if name != "__version__":
            assert getattr(pain001, name) is not None, name
    assert set(pain001.__all__) <= set(dir(pain001))


def test_parquet_support_is_probed_without_importing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import importlib.util

    lpd = importlib.import_module("pain001.parquet.load_parquet_data")

    def refuse(name: str) -> None:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib.util, "find_spec", refuse)
    assert lpd._installed("pyarrow") is False
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert lpd._installed("pyarrow") is False
