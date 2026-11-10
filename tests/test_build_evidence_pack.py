# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The release evidence pack: contents, checksums and determinism."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_evidence_pack as pack  # noqa: E402

VERSION = "9.9.9"
PREFIX = f"pain001-{VERSION}-evidence-pack/"


def _sums(directory: Path, names: list[str]) -> None:
    lines = [
        f"{hashlib.sha256((directory / n).read_bytes()).hexdigest()}  {n}"
        for n in names
    ]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n")


@pytest.fixture
def assets(tmp_path: Path) -> Path:
    """A release asset directory consistent with its SHA256SUMS."""
    directory = tmp_path / "assets"
    directory.mkdir()
    (directory / f"pain001-{VERSION}.cdx.json").write_text('{"bom": 1}')
    (directory / "multiple.intoto.jsonl").write_text('{"payload": "x"}\n')
    _sums(directory, [f"pain001-{VERSION}.cdx.json"])
    return directory


def _names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def test_the_pack_holds_documents_assets_and_a_manifest(
    assets: Path, tmp_path: Path
) -> None:
    built = pack.build(VERSION, assets, tmp_path / "out")
    assert built.name == f"pain001-{VERSION}-evidence-pack.zip"
    names = _names(built)
    assert PREFIX + "MANIFEST.json" in names
    assert PREFIX + "documents/docs/evidence/data-handling.md" in names
    assert PREFIX + "documents/docs/maintenance-policy.md" in names
    assert PREFIX + f"release-assets/pain001-{VERSION}.cdx.json" in names
    assert PREFIX + "release-assets/multiple.intoto.jsonl" in names
    with zipfile.ZipFile(built) as zf:
        manifest = json.loads(zf.read(PREFIX + "MANIFEST.json"))
        for item in manifest["files"]:
            data = zf.read(PREFIX + item["path"])
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
            assert len(data) == item["bytes"]
    assert manifest["version"] == VERSION
    assert len(manifest["files"]) == len(names) - 1


def test_the_same_inputs_give_the_same_bytes(
    assets: Path, tmp_path: Path
) -> None:
    first = pack.build(VERSION, assets, tmp_path / "a").read_bytes()
    second = pack.build(VERSION, assets, tmp_path / "b").read_bytes()
    assert first == second


def test_optional_assets_are_taken_when_present(
    assets: Path, tmp_path: Path
) -> None:
    (assets / f"pain001-{VERSION}.cdx.xml").write_text("<bom/>")
    built = pack.build(VERSION, assets, tmp_path / "out")
    assert PREFIX + f"release-assets/pain001-{VERSION}.cdx.xml" in _names(
        built
    )


def test_a_missing_required_asset_is_refused(
    assets: Path, tmp_path: Path
) -> None:
    (assets / "multiple.intoto.jsonl").unlink()
    with pytest.raises(pack.EvidencePackError, match="multiple.intoto.jsonl"):
        pack.build(VERSION, assets, tmp_path / "out")


def test_an_asset_that_differs_from_sha256sums_is_refused(
    assets: Path, tmp_path: Path
) -> None:
    (assets / f"pain001-{VERSION}.cdx.json").write_text('{"bom": 2}')
    with pytest.raises(
        pack.EvidencePackError, match="differs from SHA256SUMS"
    ):
        pack.build(VERSION, assets, tmp_path / "out")


def test_extra_files_go_under_external(assets: Path, tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    scorecard.write_text('{"score": 8.4}')
    built = pack.build(
        VERSION,
        assets,
        tmp_path / "out",
        [f"openssf-scorecard.json={scorecard}"],
    )
    assert PREFIX + "external/openssf-scorecard.json" in _names(built)


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ("no-equals-sign", "expects name=path"),
        ("=path", "expects name=path"),
        ("name=", "expects name=path"),
        ("a/b=path", "expects name=path"),
        ("name=/does/not/exist", "not found"),
    ],
)
def test_bad_extra_files_are_refused(spec: str, message: str) -> None:
    with pytest.raises(pack.EvidencePackError, match=message):
        pack.include_entries([spec])


def test_a_missing_document_is_refused(
    assets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pack, "DOCUMENTS", ("docs/evidence/absent.md",))
    with pytest.raises(pack.EvidencePackError, match="absent.md"):
        pack.build(VERSION, assets, tmp_path / "out")


def test_sha256sums_lines_are_read_in_either_mode() -> None:
    sums = pack.parse_sums("aa  text.txt\nbb  *binary.bin\n\nmalformed\n")
    assert sums == {"text.txt": "aa", "binary.bin": "bb"}


def test_main_prints_the_pack(
    assets: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    code = pack.main(
        ["--version", VERSION, "--assets", str(assets), "--out", str(out)]
    )
    assert code == 0
    assert capsys.readouterr().out.strip().endswith("evidence-pack.zip")


def test_main_reports_why_it_cannot_build(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = pack.main(
        [
            "--version",
            VERSION,
            "--assets",
            str(tmp_path),
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 1
    assert "missing release assets" in capsys.readouterr().err
