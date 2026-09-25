# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Keep documentation sources aligned with executable repository contracts."""

import re
import subprocess
import sys
from pathlib import Path

from scripts.render_readme import render

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_deployment_build_uses_locked_extras_and_runs_on_prs() -> None:
    """Exercise the deployment build before merging, with importable APIs."""
    workflow = (ROOT / ".github/workflows/docs.yml").read_text()
    assert "  pull_request:\n    branches: [main]" in workflow
    assert (
        "poetry install --no-interaction --only main,docs --all-extras"
        in workflow
    )
    assert "poetry run sphinx-build -W --keep-going" in workflow
    assert "github.event_name != 'pull_request'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow


def test_readme_is_current_and_has_canonical_headings() -> None:
    """Generated output retains the mandatory canonical section ordering."""
    text = (ROOT / "README.md").read_text()
    assert text == render()
    assert not re.search(r"\{\{[A-Z_]+\}\}", text)
    assert re.findall(r"^## (.+)$", text, re.MULTILINE) == [
        "Contents",
        "Install",
        "Requirements",
        "Quick Start",
        "The Pain001 ecosystem",
        "Capabilities at a glance",
        "Ecosystem comparison",
        "Benchmarks",
        "Features",
        "Configuration",
        "Examples",
        "When not to use Pain001",
        "Development",
        "Security",
        "Documentation",
        "Stability guarantees",
        "License",
    ]
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if "://" not in link and not link.startswith("#"):
            assert (ROOT / link.split("#")[0]).exists(), link
            with (ROOT / "pyproject.toml").open("rb") as source:
                copied = tomllib.load(source)["tool"]["mutmut"]["also_copy"]
            assert link.split("#")[0].split("/")[0] in copied, link


def test_readme_quick_start_runs_verbatim(tmp_path: Path) -> None:
    """Execute the actual documented commands in an empty directory."""
    text = (ROOT / "README.md").read_text()
    section = text.split("## Quick Start\n", 1)[1].split("\n---", 1)[0]
    commands = re.search(r"```bash\n(.*?)\n```", section, re.DOTALL)
    assert commands is not None
    for command in commands[1].splitlines():
        words = command.split()
        assert words[0] == "pain001"
        subprocess.run(
            [sys.executable, "-m", "pain001", *words[1:]],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    assert list((tmp_path / "output").glob("*.xml"))


def test_current_guides_state_current_quality_floor() -> None:
    """Contributor and landing pages cannot silently revert old policy."""
    for name in ("CONTRIBUTING.md", "docs/index.rst", "docs/faq.rst"):
        text = (ROOT / name).read_text()
        assert "95%" not in text
        assert "Python 3.9" not in text
        assert "100%" in text


def test_security_lists_immediately_previous_release() -> None:
    """Correcting version sync must also preserve the support window."""
    from pain001 import __version__

    major, minor, patch = map(int, __version__.split("."))
    previous = f"{major}.{minor}.{patch - 1}"
    assert f"| `{previous}` | Prior |" in (ROOT / "SECURITY.md").read_text()
