# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Assemble a release's evidence pack for bank reviewers.

The pack is one ZIP a risk, security or procurement reviewer can
download without a form: the review documents in ``docs/evidence/``,
the maintenance and security policies, the licence texts, the
release's SBOM, provenance and checksums, and any extra files the
release job fetched (the OpenSSF Scorecard result, the website's
``security.txt`` and accessibility statement).

Every release asset in the pack is checked against the release's own
``SHA256SUMS``, so the pack can only carry the bytes the provenance
covers. ``MANIFEST.json`` lists the SHA-256 of every file in the pack.
The ZIP is deterministic: sorted entries and a fixed timestamp, so the
same inputs give the same bytes.

Usage::

    python scripts/build_evidence_pack.py --version 0.0.85 \\
        --assets release/ --out dist-evidence/ \\
        --include openssf-scorecard.json=scorecard.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = (
    "docs/evidence/index.md",
    "docs/evidence/data-handling.md",
    "docs/evidence/verify-a-release.md",
    "docs/evidence/dora-evidence-map.md",
    "docs/evidence/licence-summary.md",
    "docs/evidence/security-questionnaire.csv",
    "docs/maintenance-policy.md",
    "SECURITY.md",
    "SUPPORT.md",
    "LICENSE",
    "LICENSE-APACHE",
    "LICENSE-MIT",
)
REQUIRED_ASSETS = (
    "{name}-{version}.cdx.json",
    "multiple.intoto.jsonl",
    "SHA256SUMS",
)
OPTIONAL_ASSETS = (
    "{name}-{version}.cdx.xml",
    "{name}-{version}.spdx-licenses.json",
)
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


class EvidencePackError(Exception):
    """The pack cannot be built from these inputs."""


@dataclass(frozen=True)
class Entry:
    """One file in the pack: where it goes and where it comes from."""

    arcname: str
    source: Path


def sha256(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_sums(text: str) -> dict[str, str]:
    """Map file name to digest from ``sha256sum`` output.

    Args:
        text: Lines of ``<digest>  <name>`` (a leading ``*`` on the name,
            binary mode, is accepted).

    Returns:
        The digest of each named file.
    """
    sums = {}
    for line in text.splitlines():
        digest, _, name = line.strip().partition("  ")
        if digest and name:
            sums[name.lstrip("*")] = digest
    return sums


def document_entries(root: Path) -> list[Entry]:
    """The review documents and policies, which must all exist.

    Args:
        root: The repository root.

    Returns:
        One entry per document, under ``documents/``.

    Raises:
        EvidencePackError: A document is missing.
    """
    missing = [d for d in DOCUMENTS if not (root / d).is_file()]
    if missing:
        raise EvidencePackError(f"missing documents: {', '.join(missing)}")
    return [Entry(f"documents/{d}", root / d) for d in DOCUMENTS]


def _asset_names(assets: Path, name: str, version: str) -> list[str]:
    """The required asset names, then the optional ones that exist.

    Args:
        assets: The directory the release assets were downloaded to.
        name: The project name, as in the asset file names.
        version: The release version.

    Returns:
        The asset file names to pack.

    Raises:
        EvidencePackError: A required asset is missing.
    """
    names = [t.format(name=name, version=version) for t in REQUIRED_ASSETS]
    missing = [n for n in names if not (assets / n).is_file()]
    if missing:
        raise EvidencePackError(
            f"missing release assets: {', '.join(missing)}"
        )
    optional = [t.format(name=name, version=version) for t in OPTIONAL_ASSETS]
    return names + [n for n in optional if (assets / n).is_file()]


def _check_sums(assets: Path, names: Sequence[str]) -> None:
    """Refuse an asset whose digest differs from the release's SHA256SUMS.

    Args:
        assets: The directory holding the assets and ``SHA256SUMS``.
        names: The asset names to check; names SHA256SUMS omits pass.

    Raises:
        EvidencePackError: A digest differs.
    """
    sums = parse_sums((assets / "SHA256SUMS").read_text(encoding="utf-8"))
    wrong = [n for n in names if n in sums and sums[n] != sha256(assets / n)]
    if wrong:
        raise EvidencePackError(
            f"digest differs from SHA256SUMS: {', '.join(wrong)}"
        )


def asset_entries(assets: Path, name: str, version: str) -> list[Entry]:
    """The release assets, each checked against the release's SHA256SUMS.

    Args:
        assets: The directory the release assets were downloaded to.
        name: The project name, as in the asset file names.
        version: The release version.

    Returns:
        One entry per asset found, under ``release-assets/``.
    """
    names = _asset_names(assets, name, version)
    _check_sums(assets, names)
    return [Entry(f"release-assets/{n}", assets / n) for n in names]


def include_entries(specs: Sequence[str]) -> list[Entry]:
    """Extra files given as ``name=path``, placed under ``external/``.

    Args:
        specs: ``name=path`` pairs; ``name`` is the file name in the pack.

    Returns:
        One entry per extra file.

    Raises:
        EvidencePackError: A pair is malformed, names a nested path, or
            its file is missing.
    """
    entries = []
    for spec in specs:
        arcname, sep, source = spec.partition("=")
        if not sep or not arcname or not source or "/" in arcname:
            raise EvidencePackError(
                f"--include expects name=path, got {spec!r}"
            )
        path = Path(source)
        if not path.is_file():
            raise EvidencePackError(f"--include file not found: {source}")
        entries.append(Entry(f"external/{arcname}", path))
    return entries


def manifest(version: str, entries: Sequence[Entry]) -> bytes:
    """``MANIFEST.json``: every file in the pack with its SHA-256 and size."""
    files = [
        {
            "path": e.arcname,
            "sha256": sha256(e.source),
            "bytes": e.source.stat().st_size,
        }
        for e in sorted(entries, key=lambda e: e.arcname)
    ]
    body = {"project": "pain001", "version": version, "files": files}
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode()


def _add(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    """Write one deterministic entry (fixed time, 0644, deflated)."""
    info = zipfile.ZipInfo(arcname, date_time=FIXED_TIME)
    info.external_attr = 0o644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, data)


def build(
    version: str, assets: Path, out: Path, includes: Sequence[str] = ()
) -> Path:
    """Write ``pain001-<version>-evidence-pack.zip`` into ``out``.

    Args:
        version: The release version.
        assets: The directory holding the release assets.
        out: The directory to write the pack to (created if absent).
        includes: Extra ``name=path`` files.

    Returns:
        The path of the pack.
    """
    entries = (
        document_entries(ROOT)
        + asset_entries(assets, "pain001", version)
        + include_entries(includes)
    )
    out.mkdir(parents=True, exist_ok=True)
    pack = out / f"pain001-{version}-evidence-pack.zip"
    prefix = f"pain001-{version}-evidence-pack/"
    with zipfile.ZipFile(pack, "w") as zf:
        _add(zf, prefix + "MANIFEST.json", manifest(version, entries))
        for entry in sorted(entries, key=lambda e: e.arcname):
            _add(zf, prefix + entry.arcname, entry.source.read_bytes())
    return pack


def _parser() -> argparse.ArgumentParser:
    """The command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--include", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build the pack and print its path; exit 1 with the reason if not.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 on success, 1 when the pack cannot be built.
    """
    args = _parser().parse_args(argv)
    try:
        pack = build(args.version, args.assets, args.out, args.include)
    except EvidencePackError as exc:
        print(f"evidence pack: {exc}", file=sys.stderr)
        return 1
    print(pack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
