# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Executable evidence for code-scanning triage and supply-chain fixes."""

import ast
import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_scheme_exports_preserve_identity_and_qualified_names() -> None:
    """Internal rule extraction preserves public objects and pickle paths."""
    from pain001.validation import _scheme_rules, schemes

    assert schemes.PROFILES is _scheme_rules.PROFILES
    assert schemes.REMEDIATIONS is _scheme_rules.REMEDIATIONS
    for name in (
        "SchemeViolation",
        "SchemeValidationResult",
        "ValidationProfile",
        "SepaCreditTransferProfile",
        "SepaDirectDebitProfile",
        "SepaB2BDirectDebitProfile",
        "SepaInstantCreditTransferProfile",
        "CrossBorderCreditTransferProfile",
        "AntiDuplicateProfile",
        "remediation_for",
    ):
        exported = getattr(schemes, name)
        assert exported is getattr(_scheme_rules, name)
        assert exported.__module__ == "pain001.validation.schemes"
        assert (
            getattr(importlib.import_module(exported.__module__), name)
            is exported
        )


@pytest.mark.parametrize(
    "relative",
    [
        "plugins/_builtins.py",
        "plugins/builtins_gpg.py",
        "validation/_scheme_rules.py",
        "validation/rails.py",
    ],
)
def test_builtin_rules_do_not_import_registry_dispatch(relative: str) -> None:
    """Registration dependencies never point back at the dispatch facade."""
    tree = ast.parse((ROOT / "pain001" / relative).read_text())
    forbidden = {"pain001.plugins.registry", "pain001.validation.schemes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden
        elif isinstance(node, ast.Import):
            assert not forbidden.intersection(
                alias.name for alias in node.names
            )


@pytest.mark.parametrize("extra", [None, "api"])
def test_runtime_locks_satisfy_package_metadata(extra: str | None) -> None:
    """Container and CI pins cannot silently lag declared dependency floors."""
    with (ROOT / "pyproject.toml").open("rb") as source:
        poetry = tomllib.load(source)["tool"]["poetry"]
    lock = ROOT / (
        ".github/requirements/api.txt" if extra else "requirements.txt"
    )
    pins = {
        canonicalize_name(name): version
        for name, version in re.findall(
            r"^([\w.-]+)==([^\s\\]+)", lock.read_text(), re.MULTILINE
        )
    }
    extra_names = poetry["extras"].get(extra, [])
    for name, value in poetry["dependencies"].items():
        if name == "python":
            continue
        if isinstance(value, dict):
            if value.get("optional") and name not in extra_names:
                continue
            specifier = value["version"]
        else:
            specifier = value
        requirement = Requirement(f"{name}{specifier}")
        pinned = pins[canonicalize_name(name)]
        assert requirement.specifier.contains(pinned), (
            name,
            pinned,
            specifier,
        )


def test_public_exports_resolve_without_eager_cli_import() -> None:
    """The PEP 562 main export resolves while ordinary imports stay lazy."""
    script = "\n".join(
        [
            "import sys, pain001",
            "assert 'pain001.__main__' not in sys.modules",
            "assert 'pain001.cli.cli' not in sys.modules",
            "assert all(hasattr(pain001, name) for name in pain001.__all__)",
            "from pain001.__main__ import main",
            "assert pain001.main is main",
        ]
    )
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize(
    "module",
    [
        "pain001.plugins.registry",
        "pain001.plugins._builtins",
        "pain001.plugins.builtins_gpg",
    ],
)
def test_plugin_import_and_population_in_fresh_interpreter(
    module: str,
) -> None:
    """Lazy registry composition works regardless of the first import."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"import {module}; "
            "from pain001.plugins.registry import registry; "
            "assert registry.get_loader('csv') is not None; "
            "assert registry.get_writer('xml-file') is not None",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_workflow_python_installs_are_hash_locked_or_offline() -> None:
    """Network installs use hashes and local builds cannot resolve backends."""
    sources = [
        ROOT / "Dockerfile",
        *sorted((ROOT / ".github/workflows").glob("*.yml")),
    ]
    for source in sources:
        for line in source.read_text().splitlines():
            if line.lstrip().startswith("#"):
                continue
            if "pip install " in line:
                assert "--require-hashes" in line, source.name
            if "-m build " in line:
                assert "--no-isolation" in line, source.name
                assert "PIP_NO_INDEX=1" in line, source.name


def test_actions_use_hashes_except_required_slsa_release_tag() -> None:
    """Only the upstream-required SLSA generator identity uses a tag."""
    slsa = (
        "slsa-framework/slsa-github-generator/.github/workflows/"
        "generator_generic_slsa3.yml@v2.1.0"
    )
    for source in (ROOT / ".github/workflows").glob("*.yml"):
        for action in re.findall(r"\buses:\s*([^\s#]+)", source.read_text()):
            assert (
                action.startswith("./")
                or re.fullmatch(r"[^@]+@[0-9a-f]{40}", action)
                or action == slsa
            ), f"Mutable action in {source.name}: {action}"
