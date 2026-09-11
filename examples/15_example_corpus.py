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

"""The example corpus, end to end: every feature it ships.

Two corpora ship in the wheel, built by one engine (ADR-0003):
realistic **market files** per country and rail with a provenance
record beside each, and **schema coverage sets** that exercise every
element and choice branch of every bundled edition. This script walks
the whole surface:

1. the read API (``list_files``, ``get_file``, ``provenance``,
   ``coverage_report``) and the coverage manifest;
2. the schema inventory and the coverage measurement on your own file;
3. synthetic identifiers that pass their check digits;
4. building a scenario in any edition, with a private overlay patch
   the way a reader applies their own bank's guideline;
5. the four-rung validation ladder (XSD, ISO MDR rules, rail profile,
   overlay) and the projection that feeds a rail profile;
6. the ISO external code sets;
7. the guideline derive tool on a synthetic guideline kept outside the
   repository;
8. generating the newest bundled type, ``pain.008.001.08``, from its
   template.

Nothing here touches a real bank's material: the overlay and the
guideline are illustrative, written by this script.

Run from the repository root::

    python examples/15_example_corpus.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from pain001 import generate_xml_string, validate_scheme
from pain001.constants import TEMPLATES_DIR
from pain001.corpus import (
    build,
    coverage,
    coverage_report,
    get_file,
    inventory_for,
    list_files,
    load_scenarios,
    present_paths,
    provenance,
)
from pain001.corpus import identifiers as ids
from pain001.corpus.rules import external_codes
from pain001.corpus.rules.ladder import ladder_passes, run_ladder
from pain001.corpus.rules.overlays import overlay_from
from pain001.corpus.rules.projection import rows_from_xml
from pain001.csv.load_csv_data import load_csv_data
from pain001.templates import DEFAULT_TEMPLATE_REGISTRY

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import derive_overlay  # noqa: E402

SCENARIO = "gb.chaps.property-purchase"
EDITION = "pain.001.001.09"


def _read_api() -> None:
    """1. What ships, what one file says about itself, and the coverage verdict."""
    market = list_files("market")
    sets = list_files("coverage")
    countries = sorted({f.country for f in market})
    print(
        f"corpus: {len(market)} market files across {len(countries)} countries, "
        f"{len(sets)} coverage files"
    )
    xml = get_file(SCENARIO, EDITION)
    assert xml.startswith("<?xml") and "<Purp>" in xml
    record = provenance(SCENARIO, EDITION)
    assert record["validation"]["xsd"]["errors"] == 0
    assert record["provenance"]["confidence"] in {
        "verified",
        "derived",
        "assumed",
    }
    print(
        f"{SCENARIO} in {EDITION}: confidence {record['provenance']['confidence']}, "
        f"sha256 {record['sha256'][:12]}…"
    )
    report = coverage_report("pain.001.001.13")
    assert report["complete"]
    first = report["files"][0]
    assert first["name"] == "01-transfer-every-element.xml"
    print(
        f"coverage pain.001.001.13: {len(report['files'])} files; "
        f"{first['name']}: {first['description'][:60]}…"
    )


def _inventory_and_coverage() -> None:
    """2. Measure your own file against the schema inventory."""
    inventory = inventory_for(EDITION)
    xml = get_file(SCENARIO, EDITION)
    used = present_paths(xml)
    verdict = coverage(inventory, [xml])
    assert 0 < len(used) < len(inventory.paths())
    assert not verdict.complete and verdict.path_percent < 100
    print(
        f"inventory {EDITION}: {len(inventory.paths())} paths, "
        f"{len(inventory.choices)} choices; one CHAPS file uses "
        f"{len(used)} paths ({verdict.path_percent:.1f} %)"
    )


def _identifiers() -> None:
    """3. Synthetic identifiers that pass every check and belong to nobody."""
    iban = ids.iban_for("CH", seed=7)
    bic = ids.make_bic("GB", seed=7)
    lei = ids.make_lei(7)
    assert (
        ids.iban_is_valid(iban)
        and ids.bic_is_test(bic)
        and ids.lei_is_valid(lei)
    )
    assert ids.iban_for("CH", seed=7) == iban, "deterministic per seed"
    print(f"identifiers: IBAN {iban}, test BIC {bic}, LEI {lei}")


def _build_with_private_overlay() -> dict:
    """4. Render a scenario, then apply an illustrative private overlay.

    The overlay is the shape a reader writes from their own bank's usage
    guideline and keeps in their own environment.
    """
    scenario = {s.id: s for s in load_scenarios()}[SCENARIO]
    generic = build(scenario, "pain.001.001.03")
    assert generic.xml.startswith("<?xml")
    overlay = overlay_from(
        {
            "overlay_id": "gb.example.priority",
            "title": "Illustrative priority profile (not a real bank)",
            "applies_to": [SCENARIO],
            "versions": ["pain.001.001.03"],
            "patch": {
                "payment": {
                    "type": {"service_level": "URNS"},
                    "debtor": {
                        "address": {
                            "form": "structured",
                            "country_subdivision": "England",
                        }
                    },
                }
            },
            "rules": [
                {
                    "rule_id": "example-svclvl",
                    "description": "The service level is URNS.",
                    "locator": "PmtTpInf/SvcLvl/Cd",
                    "assertion": "one_of:[URNS]",
                    "error_code": "EX_SVCLVL",
                },
                {
                    "rule_id": "example-subdivision",
                    "description": "The debtor address carries a subdivision.",
                    "locator": "Dbtr/PstlAdr/CtrySubDvsn",
                    "assertion": "required",
                    "error_code": "EX_SUBDIV",
                },
            ],
        }
    )
    variant = build(scenario, "pain.001.001.03", overlay.patch_for(SCENARIO))
    assert (
        "<Cd>URNS</Cd>" in variant.xml and "<Cd>URNS</Cd>" not in generic.xml
    )
    print(
        "build: generic .03 and a private variant with URNS and a subdivision"
    )
    return {
        "scenario": scenario,
        "overlay": overlay,
        "generic": generic,
        "variant": variant,
    }


def _ladder(built: dict) -> None:
    """5. Four rungs on the variant; the generic file fails the private rules."""
    scenario, overlay = built["scenario"], built["overlay"]
    record = run_ladder(
        scenario,
        "pain.001.001.03",
        built["variant"].xml,
        [overlay],
        overlay.overlay_id,
    )
    assert ladder_passes(record)
    assert record["overlays"]["gb.example.priority"]["errors"] == 0
    failed = run_ladder(
        scenario,
        "pain.001.001.03",
        built["generic"].xml,
        [overlay],
        overlay.overlay_id,
    )
    assert not ladder_passes(failed)
    codes = [
        f.split(":")[0]
        for f in failed["overlays"]["gb.example.priority"]["findings"]
    ]
    print(f"ladder: variant passes L0-L3; generic breaks {codes}")

    # The rail profile (L2) reads the file through the same projection the
    # scheme validator uses, so a CSV row and a built XML are judged alike.
    rows = rows_from_xml(get_file(SCENARIO, EDITION))
    result = validate_scheme(rows, profile="uk-chaps,purpose-mandate-gb")
    assert result.is_valid
    print(
        f"rail profile uk-chaps on the shipped file: valid, {len(rows)} row(s)"
    )


def _external_codes() -> None:
    """6. The ISO external code sets the validators check against."""
    edition = external_codes.edition()
    sets = external_codes.code_sets()
    assert "ExternalPurpose1Code" in sets
    assert external_codes.is_valid("ExternalPurpose1Code", "HLST")
    assert not external_codes.is_valid("ExternalPurpose1Code", "NOPE")
    print(
        f"external codes {edition}: {len(sets)} sets; "
        f"HLST = {external_codes.describe('ExternalPurpose1Code', 'HLST')}"
    )


def _derive_tool() -> None:
    """7. Turn a guideline schema into overlay rules, outside the repository.

    A real usage guideline is your bank's document under its own terms;
    this one is synthetic (the ISO schema with three edits) and written
    under the system temp directory, where a real export would live.
    """
    base = DEFAULT_TEMPLATE_REGISTRY.get_template("pain.001.001.03").xsd_path
    text = base.read_text(encoding="utf-8")
    text = re.sub(
        r'<xs:element name="EqvtAmt" type="EquivalentAmount2"/>', "", text
    )
    text = (
        text.replace(
            '<xs:element name="Cd" type="ExternalServiceLevel1Code"/>',
            '<xs:element name="Cd" type="RestrictedServiceLevel"/>',
            1,
        )
        + ""
    )
    text = text.replace(
        "</xs:schema>",
        '<xs:simpleType name="RestrictedServiceLevel"><xs:restriction '
        'base="xs:string"><xs:enumeration value="URNS"/></xs:restriction>'
        "</xs:simpleType></xs:schema>",
    )
    outside = Path(
        tempfile.mkdtemp(prefix="pain001-example-guideline-", dir="/tmp")
    )
    guideline = outside / "guideline.xsd"
    guideline.write_text(text, encoding="utf-8")
    changes = derive_overlay.diff(guideline, "pain.001.001.03")
    rules = derive_overlay.as_rules(changes)
    assert ("PmtInf/CdtTrfTxInf/Amt/EqvtAmt",) in changes["removed"]
    assert any("URNS" in r for r in rules)
    print(
        f"derive tool: {len(changes['removed'])} removed, "
        f"{len(changes['enum'])} narrowed code list(s); {len(rules)} rule(s) drafted"
    )
    assert (
        derive_overlay.main([str(base), "--base", "pain.001.001.03"]) != 0
    ), "an in-repository path is refused"


def _pain008_v08() -> None:
    """8. The newest bundled type renders from its own template."""
    message_type = "pain.008.001.08"
    template_dir = Path(TEMPLATES_DIR) / message_type
    data = load_csv_data(str(template_dir / "template.csv"))
    xml = generate_xml_string(
        data,
        message_type,
        str(template_dir / "template.xml"),
        str(template_dir / f"{message_type}.xsd"),
    )
    assert "CstmrDrctDbtInitn" in xml
    print(f"generated {message_type}: {len(xml)} characters, XSD-valid")


def main() -> None:
    """Run every section back to back."""
    _read_api()
    _inventory_and_coverage()
    _identifiers()
    built = _build_with_private_overlay()
    _ladder(built)
    _external_codes()
    _derive_tool()
    _pain008_v08()
    print("Example corpus example completed.")


if __name__ == "__main__":
    main()
