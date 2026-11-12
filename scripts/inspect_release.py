# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Inspect wheel/sdist bytes and prepare checksum-bearing release notes.

Run before publication, then again with --tag after signing locally. Output
belongs outside the package source to avoid self-referential archive hashes.
"""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path

Files = dict[str, bytes]


def _wheel_contents(artifact: Path) -> tuple[Files, list[bytes], str]:
    """A wheel's files, its METADATA records, and its (empty) root prefix."""
    with zipfile.ZipFile(artifact) as archive:
        files = {
            n: archive.read(n)
            for n in archive.namelist()
            if not n.endswith("/")
        }
    metadata = [
        value
        for key, value in files.items()
        if key.endswith(".dist-info/METADATA")
    ]
    return files, metadata, ""


def _sdist_contents(
    artifact: Path, root: Path
) -> tuple[Files, list[bytes], str]:
    """An sdist's files, PKG-INFO and root prefix; its sources must be current."""
    with tarfile.open(artifact, "r:gz") as archive:
        files = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"unreadable member: {member.name}")
                files[member.name] = stream.read()
    prefixes = {key.split("/")[0] for key in files}
    if len(prefixes) != 1:
        raise ValueError("source archive has multiple roots")
    prefix = prefixes.pop() + "/"
    metadata = [files[prefix + "PKG-INFO"]]
    for filename in ("pyproject.toml", "README.md"):
        if files[prefix + filename] != (root / filename).read_bytes():
            raise ValueError(f"stale packaged {filename}")
    return files, metadata, prefix


def _check_metadata(
    artifact: Path, metadata: list[bytes], name: str, version: str, readme: str
) -> None:
    """One metadata record naming this package, version and README."""
    if len(metadata) != 1:
        raise ValueError("expected exactly one distribution metadata record")
    message = email.parser.BytesParser().parsebytes(metadata[0])
    if (
        message["Name"].replace("_", "-").lower() != name.lower()
        or message["Version"] != version
    ):
        raise ValueError(f"incorrect package identity: {artifact.name}")
    if message.get_payload(decode=True).decode("utf-8").strip() != readme:
        raise ValueError(f"stale packaged README: {artifact.name}")


def _check_payload(
    artifact: Path, files: Files, prefix: str, package: str, version: str
) -> None:
    """The runtime version and a licence are packaged; never scratch data."""
    init = files[prefix + package + "/__init__.py"].decode()
    if not re.search(rf'^__version__ = "{re.escape(version)}"$', init, re.M):
        raise ValueError(f"incorrect runtime version: {artifact.name}")
    if not any("license" in key.lower() for key in files):
        raise ValueError(f"missing packaged licence: {artifact.name}")


def _sha256_line(path: Path) -> str:
    """A ``sha256sum``-style line for one file."""
    return f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"


def inspect(dist: Path, root: Path, name: str, version: str) -> list[str]:
    """Validate both distributions against their source metadata and README."""
    wheels = sorted(dist.glob("*.whl"))
    sources = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("expected exactly one wheel and one source archive")
    readme = (root / "README.md").read_text().strip()
    package = name.replace("-", "_")
    hashes = []
    for artifact in wheels + sources:
        if artifact in wheels:
            files, metadata, prefix = _wheel_contents(artifact)
        else:
            files, metadata, prefix = _sdist_contents(artifact, root)
        if any(key.startswith(prefix + package + "/tmp/") for key in files):
            raise ValueError(
                f"runtime scratch data leaked into {artifact.name}"
            )
        _check_metadata(artifact, metadata, name, version, readme)
        _check_payload(artifact, files, prefix, package, version)
        hashes.append(_sha256_line(artifact))
    return hashes


def verify_tag(root: Path, tag: str, project: str, version: str) -> None:
    """Verify the signed annotated tag and its exact main-branch target."""

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True
        ).strip()

    if tag != f"v{version}" or git("cat-file", "-t", tag) != "tag":
        raise ValueError("release requires the expected annotated tag")
    subprocess.run(["git", "-C", str(root), "verify-tag", tag], check=True)
    if git("rev-parse", f"{tag}^{{commit}}") != git("rev-parse", "HEAD"):
        raise ValueError("tag does not point to the inspected commit")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise ValueError("tag target is not origin/main")
    if git("status", "--porcelain"):
        raise ValueError("release worktree is dirty")
    first_line = git(
        "for-each-ref", "--format=%(contents:subject)", f"refs/tags/{tag}"
    )
    if first_line != f"{project} v{version}":
        raise ValueError("tag annotation does not match the release title")


def _parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """The command line, and the parser that reports a failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag")
    parser.add_argument(
        "--extra-artifacts",
        type=Path,
        help="directory containing additional release assets such as SBOMs",
    )
    return parser, parser.parse_args()


def _release_note(args: argparse.Namespace) -> str:
    """The release notes, which must name this tag and say enough."""
    body = (args.root / "releases" / f"v{args.version}.md").read_text()
    if len(body.split()) < 80 or f"v{args.version}" not in body:
        raise ValueError(
            "release notes must name this tag and summarize user-visible changes"
        )
    if args.output.resolve().is_relative_to(args.dist.resolve()):
        raise ValueError(
            "evidence must not be stored among publishable distributions"
        )
    return body


def _extra_hashes(directory: Path, hashes: list[str]) -> list[str]:
    """Checksum lines for extra release assets, uniquely named."""
    extras = sorted(directory.iterdir())
    if not extras or any(not path.is_file() for path in extras):
        raise ValueError(
            "extra artifact directory must contain release asset files"
        )
    names = {line.split()[1] for line in hashes}
    lines = []
    for path in extras:
        if path.name in names:
            raise ValueError("release asset filenames must be unique")
        names.add(path.name)
        lines.append(_sha256_line(path))
    return lines


def _write_evidence(output: Path, body: str, hashes: list[str]) -> str:
    """Write SHA256SUMS and the checksum-bearing notes; return the sums."""
    output.mkdir(parents=True, exist_ok=True)
    sums = "\n".join(hashes) + "\n"
    (output / "SHA256SUMS").write_text(sums)
    (output / "release-notes.md").write_text(
        body + "\n## SHA-256 checksums\n\n```text\n" + sums + "```\n"
    )
    return sums


def main() -> None:
    """Inspect candidate artifacts, optionally verify the tag, and emit evidence."""
    parser, args = _parse_args()
    try:
        body = _release_note(args)
        hashes = inspect(args.dist, args.root, args.name, args.version)
        if args.extra_artifacts:
            hashes += _extra_hashes(args.extra_artifacts, hashes)
        if args.tag:
            verify_tag(args.root, args.tag, args.project, args.version)
        sums = _write_evidence(args.output, body, hashes)
        print(sums, end="")
        print(
            "Artifact inspection passed"
            + (
                "; signed tag verified"
                if args.tag
                else "; tag verification still required"
            )
        )
    except (
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"Release inspection failed: {exc}\n")


if __name__ == "__main__":
    main()
