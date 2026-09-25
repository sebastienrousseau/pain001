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
            prefix = ""
        else:
            with tarfile.open(artifact, "r:gz") as archive:
                files = {}
                for member in archive.getmembers():
                    if member.isfile():
                        stream = archive.extractfile(member)
                        if stream is None:
                            raise ValueError(
                                f"unreadable member: {member.name}"
                            )
                        files[member.name] = stream.read()
            prefixes = {key.split("/")[0] for key in files}
            if len(prefixes) != 1:
                raise ValueError("source archive has multiple roots")
            prefix = prefixes.pop() + "/"
            metadata = [files[prefix + "PKG-INFO"]]
            for filename in ("pyproject.toml", "README.md"):
                if files[prefix + filename] != (root / filename).read_bytes():
                    raise ValueError(f"stale packaged {filename}")
        if len(metadata) != 1:
            raise ValueError(
                "expected exactly one distribution metadata record"
            )
        message = email.parser.BytesParser().parsebytes(metadata[0])
        if (
            message["Name"].replace("_", "-").lower() != name.lower()
            or message["Version"] != version
        ):
            raise ValueError(f"incorrect package identity: {artifact.name}")
        if message.get_payload(decode=True).decode("utf-8").strip() != readme:
            raise ValueError(f"stale packaged README: {artifact.name}")
        init = files[prefix + package + "/__init__.py"].decode()
        if not re.search(
            rf'^__version__ = "{re.escape(version)}"$', init, re.M
        ):
            raise ValueError(f"incorrect runtime version: {artifact.name}")
        if not any("license" in key.lower() for key in files):
            raise ValueError(f"missing packaged licence: {artifact.name}")
        hashes.append(
            f"{hashlib.sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}"
        )
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


def main() -> None:
    """Inspect candidate artifacts, optionally verify the tag, and emit evidence."""
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
    args = parser.parse_args()
    note = args.root / "releases" / f"v{args.version}.md"
    try:
        body = note.read_text()
        if len(body.split()) < 80 or f"v{args.version}" not in body:
            raise ValueError(
                "release notes must name this tag and summarize user-visible changes"
            )
        if args.output.resolve().is_relative_to(args.dist.resolve()):
            raise ValueError(
                "evidence must not be stored among publishable distributions"
            )
        hashes = inspect(args.dist, args.root, args.name, args.version)
        if args.extra_artifacts:
            extras = sorted(args.extra_artifacts.iterdir())
            if not extras or any(not path.is_file() for path in extras):
                raise ValueError(
                    "extra artifact directory must contain release asset files"
                )
            names = {line.split()[1] for line in hashes}
            for path in extras:
                if path.name in names:
                    raise ValueError("release asset filenames must be unique")
                names.add(path.name)
                hashes.append(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
                )
        if args.tag:
            verify_tag(args.root, args.tag, args.project, args.version)
        args.output.mkdir(parents=True, exist_ok=True)
        sums = "\n".join(hashes) + "\n"
        (args.output / "SHA256SUMS").write_text(sums)
        (args.output / "release-notes.md").write_text(
            body + "\n## SHA-256 checksums\n\n```text\n" + sums + "```\n"
        )
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
