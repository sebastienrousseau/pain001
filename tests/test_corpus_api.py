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

"""The shipped-corpus API reads the wheel's data without a checkout."""

from __future__ import annotations

import pytest

from pain001.constants import valid_xml_types
from pain001.corpus import api


def test_list_files_covers_market_and_coverage() -> None:
    """Every shipped XML is listed with its kind, version and origin."""
    everything = api.list_files()
    market = api.list_files("market")
    sets = api.list_files("coverage")
    assert len(everything) == len(market) + len(sets)
    assert {f.scenario_id for f in market} >= {
        "de.sepa.sct-salary",
        "gb.chaps.property-purchase",
        "nl.sepa.sdd-core",
    }
    gb = next(
        f
        for f in market
        if f.scenario_id == "gb.chaps.property-purchase"
        and f.version == "pain.001.001.09"
    )
    assert (gb.kind, gb.country, gb.family) == (
        "market",
        "GB",
        "priority-payment",
    )
    assert gb.read().startswith("<?xml")
    assert {f.version for f in sets} == set(valid_xml_types)
    assert all(f.scenario_id is None and f.country is None for f in sets)
    assert [f.path for f in market] == sorted(f.path for f in market)
    assert [f.path for f in sets] == sorted(f.path for f in sets)
    assert everything == market + sets


def test_get_file_provenance_and_coverage_report() -> None:
    """Lookups by scenario and edition, and the coverage verdict."""
    xml = api.get_file("nl.sepa.sdd-core", "pain.008.001.08")
    assert "CstmrDrctDbtInitn" in xml
    record = api.provenance("nl.sepa.sdd-core", "pain.008.001.08")
    assert (
        record["scenario"] == "nl.sepa.sdd-core"
        and record["message_type"] == "pain.008.001.08"
    )
    assert record["validation"]["profiles"]["sepa-sdd"]["errors"] == 0
    assert record["provenance"]["confidence"] == "derived"
    report = api.coverage_report("pain.001.001.03")
    assert report["complete"] and report["paths"]["percent"] == 100.0
    with pytest.raises(FileNotFoundError, match="no market file"):
        api.get_file("nl.sepa.sdd-core", "pain.001.001.03")
    with pytest.raises(FileNotFoundError, match="no market file"):
        api.provenance("xx.none", "pain.001.001.03")
    with pytest.raises(FileNotFoundError, match="no coverage set"):
        api.coverage_report("pain.001.001.99")


def test_list_files_without_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Missing data directories give an empty list, not an error."""
    monkeypatch.setattr(api, "MARKET_ROOT", tmp_path / "m")
    monkeypatch.setattr(api, "COVERAGE_ROOT", tmp_path / "c")
    assert api.list_files() == []
