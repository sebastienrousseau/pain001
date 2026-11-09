# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Component tables follow the checked inventory without version snapshots."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import render_ecosystem_docs as renderer
from ecosystem_audit.documentation import (
    END,
    START,
    readme_values,
    roadmap_table,
)


def test_readme_values_include_non_pypi_members() -> None:
    """The canonical renderer derives its rows from the publication inventory."""
    values = readme_values()
    urls = re.findall(r"\]\((https://[^)]+)\)", values["COMPONENT_USE_CASE"])
    assert values["COMPONENT_NAME"].startswith("[pain001](")
    assert "https://github.com/sebastienrousseau/pain001-fast" in urls
    assert "https://github.com/sebastienrousseau/pain001.github.io" in urls
    assert len(values["COMPONENT_USE_CASE"].splitlines()) == 9


def test_roadmap_preserves_prose_and_is_idempotent() -> None:
    """Generating a table must never rewrite the rest of the roadmap."""
    source = f"Before\n{START}\nstale table\n{END}\nAfter\n"
    result = roadmap_table(source)
    assert result.startswith("Before\n") and result.endswith("\nAfter\n")
    assert "stale table" not in result
    assert "GitHub Releases, PyPI, GHCR" in result
    assert "live website" in result
    assert roadmap_table(result) == result


def test_generator_writes_and_checks_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A stale checked-in table fails the CI command."""
    path = tmp_path / "ROADMAP.md"
    path.write_text(f"{START}\nwrong\n{END}\n")
    monkeypatch.setattr(renderer, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["render_ecosystem_docs.py", "--check"])
    with pytest.raises(SystemExit, match="ROADMAP is stale"):
        renderer.main()
    monkeypatch.setattr(sys, "argv", ["render_ecosystem_docs.py"])
    renderer.main()
    assert "wrong" not in path.read_text()
    monkeypatch.setattr(sys, "argv", ["render_ecosystem_docs.py", "--check"])
    renderer.main()
