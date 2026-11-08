# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``scripts/facts.py``: the release's facts come from their sources."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _facts() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "facts_script", ROOT / "scripts" / "facts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_fact_comes_from_its_source() -> None:
    from pain001 import __version__
    from pain001.cli.cli import cli
    from pain001.faces import available_faces
    from pain001.schematron import PRESET_RULEBOOKS
    from pain001.templates import DEFAULT_TEMPLATE_REGISTRY
    from pain001.validation.schemes import PROFILES

    facts = _facts().collect()
    poetry = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"][
        "poetry"
    ]
    assert facts["version"] == __version__ == poetry["version"]
    assert facts["python"] == ">=3.11"
    assert facts["extras"] == sorted(poetry["extras"])
    assert facts["message_types"] == (
        DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
    )
    assert facts["scheme_profiles"] == sorted(PROFILES)
    assert facts["schematron_rulebooks"] == sorted(PRESET_RULEBOOKS)
    assert facts["faces"] == sorted(available_faces())
    assert facts["cli_commands"] == sorted(cli.commands)  # type: ignore[attr-defined]
    counts = facts["counts"]
    assert counts["message_types"] == (
        counts["pain001_versions"] + counts["pain008_versions"]
    )
    assert counts["scheme_profiles"] == len(PROFILES)


@pytest.mark.parametrize(
    ("spec", "floor"), [("^3.11", ">=3.11"), (">=3.12,<4", ">=3.12,<4")]
)
def test_the_python_floor_reads_as_a_specifier(spec: str, floor: str) -> None:
    assert _facts()._python_floor(spec) == floor


def test_render_is_stable_json() -> None:
    facts = _facts()
    text = facts.render(facts.collect())
    assert text.endswith("\n")
    assert json.loads(text)["facts_version"] == facts.FACTS_VERSION
    assert facts.render(json.loads(text)) == text


def test_write_then_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facts = _facts()
    out = tmp_path / "facts.json"
    assert facts.main(["-o", str(out)]) == 0
    assert f"wrote {out}" in capsys.readouterr().out
    assert facts.main(["--check", str(out)]) == 0
    out.write_text("{}\n", encoding="utf-8")
    assert facts.main(["--check", str(out)]) == 1
    assert "out of date" in capsys.readouterr().err


def test_stdout_without_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert _facts().main([]) == 0
    assert json.loads(capsys.readouterr().out)["package"] == "pain001"
