# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Exercise release inspection with small synthetic wheel and sdist fixtures."""

import importlib.util
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_inspection",
    Path(__file__).resolve().parents[1] / "scripts/inspect_release.py",
)
assert SPEC is not None and SPEC.loader is not None
INSPECTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTION)


@pytest.fixture
def artifacts(tmp_path: Path) -> tuple[Path, Path]:
    """Build tiny valid archives, including non-ASCII documentation."""
    dist = tmp_path / "dist"
    dist.mkdir()
    readme = "# Sample\n\nSynthetic payment data — no real accounts.\n"
    manifest = 'version = "0.0.71"\n'
    (tmp_path / "README.md").write_text(readme)
    (tmp_path / "pyproject.toml").write_text(manifest)
    metadata = f"Metadata-Version: 2.1\nName: sample\nVersion: 0.0.71\n\n{readme}".encode()
    package = {
        "sample/__init__.py": b'__version__ = "0.0.71"\n',
        "LICENSE": b"MIT",
    }
    with zipfile.ZipFile(
        dist / "sample-0.0.71-py3-none-any.whl", "w"
    ) as archive:
        for name, content in {
            **package,
            "sample-0.0.71.dist-info/METADATA": metadata,
        }.items():
            archive.writestr(name, content)
    files = {
        **package,
        "PKG-INFO": metadata,
        "README.md": readme.encode(),
        "pyproject.toml": manifest.encode(),
    }
    with tarfile.open(dist / "sample-0.0.71.tar.gz", "w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo("sample-0.0.71/" + name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return tmp_path, dist


def test_inspects_archive_bytes_and_hashes(
    artifacts: tuple[Path, Path],
) -> None:
    """Both distributions have real SHA-256 entries and current documentation."""
    root, dist = artifacts
    hashes = INSPECTION.inspect(dist, root, "sample", "0.0.71")
    assert len(hashes) == 2
    assert all(len(line.split()[0]) == 64 for line in hashes)


@pytest.mark.parametrize("filename", ["README.md", "pyproject.toml"])
def test_stale_packaged_sources_fail(
    artifacts: tuple[Path, Path], filename: str
) -> None:
    """A worktree-only update is not evidence that the package is current."""
    root, dist = artifacts
    (root / filename).write_text("changed after building")
    with pytest.raises(ValueError, match="stale packaged"):
        INSPECTION.inspect(dist, root, "sample", "0.0.71")


def test_wrong_release_version_fails(artifacts: tuple[Path, Path]) -> None:
    """Never bless a previous release's distributions."""
    root, dist = artifacts
    with pytest.raises(ValueError, match="incorrect package identity"):
        INSPECTION.inspect(dist, root, "sample", "0.0.72")


def test_runtime_scratch_data_is_not_distributed(
    artifacts: tuple[Path, Path],
) -> None:
    """Test outputs can contain payment data and must never enter a wheel."""
    root, dist = artifacts
    with zipfile.ZipFile(next(dist.glob("*.whl")), "a") as archive:
        archive.writestr("sample/tmp/pytest/records.csv", "synthetic scratch")
    with pytest.raises(ValueError, match="runtime scratch data leaked"):
        INSPECTION.inspect(dist, root, "sample", "0.0.71")


def test_poetry_explicitly_excludes_runtime_scratch() -> None:
    """Poetry must not open test-created FIFOs while building a wheel."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert "pain001/tmp/**" in config["tool"]["poetry"]["exclude"]


def test_missing_artifacts_fail(tmp_path: Path) -> None:
    """An empty output directory cannot pass a vacuous checksum check."""
    with pytest.raises(ValueError, match="exactly one"):
        INSPECTION.inspect(tmp_path, tmp_path, "sample", "0.0.71")


def test_release_body_includes_actual_extra_asset_hashes(
    artifacts: tuple[Path, Path],
) -> None:
    """The release manifest covers SBOMs as well as installable packages."""
    root, dist = artifacts
    (root / "releases").mkdir()
    (root / "releases/v0.0.71.md").write_text(
        "# Sample v0.0.71\n\n"
        + "Documented user-visible release changes. " * 30
    )
    extras = root / "sbom"
    extras.mkdir()
    (extras / "sample.cdx.json").write_text('{"bomFormat": "CycloneDX"}')
    output = root / "evidence"
    result = subprocess.run(
        [
            sys.executable,
            str(SPEC.origin),
            "--root",
            str(root),
            "--dist",
            str(dist),
            "--output",
            str(output),
            "--name",
            "sample",
            "--project",
            "Sample",
            "--version",
            "0.0.71",
            "--extra-artifacts",
            str(extras),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    manifest = (output / "SHA256SUMS").read_text()
    assert len(manifest.splitlines()) == 3
    assert "sample.cdx.json" in manifest
    assert manifest in (output / "release-notes.md").read_text()


@pytest.mark.parametrize(
    "failure",
    ["lightweight", "target", "main", "dirty", "annotation", "signature"],
)
def test_tag_verification_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """A signed tag must describe precisely the inspected, merged commit."""

    def output(command: list[str], **kwargs: object) -> str:
        del kwargs
        args = command[3:]
        if args[:2] == ["cat-file", "-t"]:
            return "commit" if failure == "lightweight" else "tag"
        if args[0] == "status":
            return " M README.md" if failure == "dirty" else ""
        if args[0] == "for-each-ref":
            return "wrong" if failure == "annotation" else "Sample v0.0.71"
        if args[-1] == "v0.0.71^{commit}" and failure == "target":
            return "other"
        if args[-1] == "origin/main" and failure == "main":
            return "other"
        return "release-commit"

    def verify(*args: object, **kwargs: object) -> None:
        del args, kwargs
        if failure == "signature":
            raise INSPECTION.subprocess.CalledProcessError(1, "verify-tag")

    monkeypatch.setattr(INSPECTION.subprocess, "check_output", output)
    monkeypatch.setattr(INSPECTION.subprocess, "run", verify)
    with pytest.raises((ValueError, INSPECTION.subprocess.CalledProcessError)):
        INSPECTION.verify_tag(tmp_path, "v0.0.71", "Sample", "0.0.71")
