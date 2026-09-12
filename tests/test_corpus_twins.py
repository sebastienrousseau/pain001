# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""The twins the corpus ships beside its market files (ADR-0005)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from pain001.corpus import api, get_twin, list_files, provenance
from pain001.twins import SUPPORTED_PREFIX, RecordsTwin, to_iso_json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus  # noqa: E402

MARKET = list_files("market")
PAIN001 = [f for f in MARKET if f.version.startswith(SUPPORTED_PREFIX)]
OTHERS = [f for f in MARKET if not f.version.startswith(SUPPORTED_PREFIX)]
CHAPS = ("gb.chaps.property-purchase", "pain.001.001.09")


@pytest.mark.parametrize("entry", PAIN001, ids=lambda f: f.path.name)
def test_shipped_twin_matches_the_file_and_its_sidecar(entry) -> None:
    """The .iso.json beside a pain.001 file is its twin; the sidecar says so."""
    shipped = entry.path.with_suffix(".iso.json")
    assert shipped.exists()
    text = shipped.read_text(encoding="utf-8")
    assert json.loads(text) == to_iso_json(entry.read(), entry.version)
    assert text == build_corpus.twin_text(entry.read(), entry.version)
    record = yaml.safe_load(
        entry.path.with_suffix(".provenance.yaml").read_text(encoding="utf-8")
    )
    twins = record["twins"]
    assert (
        twins["iso_json"]["sha256"]
        == hashlib.sha256(text.encode()).hexdigest()
    )
    assert twins["iso_json"]["schema_findings"] == []
    assert twins["records"]["rows"] >= 1
    assert isinstance(twins["records"]["gap"], list)
    assert isinstance(twins["records"]["missing_required"], list)


@pytest.mark.parametrize("entry", OTHERS, ids=lambda f: f.path.name)
def test_files_outside_the_scope_ship_no_twin(entry) -> None:
    """pain.008 files have no twin file and a null twins block."""
    assert not entry.path.with_suffix(".iso.json").exists()
    record = yaml.safe_load(
        entry.path.with_suffix(".provenance.yaml").read_text(encoding="utf-8")
    )
    assert record["twins"] is None
    assert build_corpus.twins_for(entry.read(), entry.version) is None


def test_get_twin_and_corpus_file_twin() -> None:
    """The API serves the shipped twin, computes one when absent, and records."""
    twin = get_twin(*CHAPS)
    assert set(twin) == {"Document"}
    entry = next(f for f in PAIN001 if (f.scenario_id, f.version) == CHAPS)
    assert entry.twin() == twin
    records = get_twin(*CHAPS, "records")
    assert isinstance(records, RecordsTwin) and len(records.rows) == 1
    coverage_entry = next(
        f for f in list_files("coverage") if f.version == "pain.001.001.09"
    )
    computed = coverage_entry.twin()
    assert "Document" in computed, "computed on demand, nothing shipped"
    assert not coverage_entry.path.with_suffix(".iso.json").exists()
    with pytest.raises(ValueError, match="unknown twin format"):
        entry.twin("yaml")
    with pytest.raises(FileNotFoundError):
        get_twin("nobody", "pain.001.001.09")
    assert provenance(*CHAPS)["twins"]["records"]["rows"] == 1


def test_no_orphan_twins() -> None:
    """Every shipped .iso.json belongs to a pain.001 market file."""
    for path in api.MARKET_ROOT.rglob("*.iso.json"):
        xml = path.with_name(path.name.replace(".iso.json", ".xml"))
        assert xml.exists(), path
        assert ".pain.001." in path.name
