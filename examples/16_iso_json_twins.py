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

"""Twins: the same pain.001 message, losslessly, in JSON (ADR-0005).

1. The ISO JSON twin of a corpus file, in the ISO 20022 Registration
   Authority's 2025 convention, and its round trip back to XML.
2. Validation against the edition's JSON Schema 2020-12, and what the
   schema rejects.
3. Editing the payment in JSON and encoding it through the XSD.
4. The records twin: the CSV pipeline's flat rows, the measured gap,
   and regeneration through the pipeline where nothing is missing.

Run from the repository root::

    python examples/16_iso_json_twins.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR
from pain001.corpus import get_file, get_twin
from pain001.twins import (
    column_paths,
    from_iso_json,
    iso_json_schema,
    to_iso_json,
    to_records,
    validate_iso_json,
)

SCENARIO, EDITION = "gb.chaps.property-purchase", "pain.001.001.09"


def _twin_and_back() -> dict:
    """1. The twin has the RA shape and comes back as the same document."""
    xml = get_file(SCENARIO, EDITION)
    twin = to_iso_json(xml, EDITION)
    assert twin == get_twin(SCENARIO, EDITION), "the shipped .iso.json"
    tx = twin["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["CdtTrfTxInf"][0]
    assert tx["Amt"]["InstdAmt"] == {"amt": "425000.00", "Ccy": "GBP"}
    back = from_iso_json(twin, EDITION)
    assert to_iso_json(back, EDITION) == twin
    print(
        f"twin: {len(json.dumps(twin))} bytes of JSON for {len(xml)} of XML; "
        "round trip equal"
    )
    return twin


def _schema(twin: dict) -> None:
    """2. The per-edition schema accepts the twin and rejects what the RA rejects."""
    schema = iso_json_schema(EDITION)
    assert schema["$id"] == f"urn:iso:std:iso:20022:tech:json:{EDITION}"
    assert validate_iso_json(twin, EDITION) == []
    bad = copy.deepcopy(twin)
    bad["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["CdtTrfTxInf"][0]["Amt"][
        "InstdAmt"
    ]["amt"] = "1.123456"
    findings = validate_iso_json(bad, EDITION)
    assert findings and "InstdAmt/amt" in findings[0]
    print(
        f"schema: {len(schema['$defs'])} definitions; six decimals rejected at "
        f"{findings[0].split(':')[0]}"
    )


def _edit_in_json() -> None:
    """3. Change the amount in JSON; the XSD guards the way back."""
    twin = get_twin(SCENARIO, EDITION)
    tx = twin["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["CdtTrfTxInf"][0]
    tx["Amt"]["InstdAmt"]["amt"] = "425500.00"
    twin["Document"]["CstmrCdtTrfInitn"]["GrpHdr"]["CtrlSum"] = "425500.00"
    twin["Document"]["CstmrCdtTrfInitn"]["PmtInf"][0]["CtrlSum"] = "425500.00"
    xml = from_iso_json(twin, EDITION)
    assert '<InstdAmt Ccy="GBP">425500.00</InstdAmt>' in xml
    try:
        tx["Nope"] = "x"
        from_iso_json(twin, EDITION)
    except Exception as exc:  # TwinError
        print(
            f"edit: amount changed and re-encoded; an unknown element raises "
            f"{type(exc).__name__}"
        )


def _records() -> None:
    """4. The pipeline's rows, the measured gap, and regeneration."""
    xml = get_file(SCENARIO, EDITION)
    records = to_records(xml, EDITION)
    assert records.missing_required == []
    row = records.rows[0]
    print(
        f"records: {len(row)} columns for 1 transaction; the pipeline cannot "
        f"carry {len(records.gap)} paths, e.g. {records.gap[1]}"
    )
    mapping = column_paths(EDITION)
    print(
        f"  {len([c for c, p in mapping.items() if p])} of {len(mapping)} "
        "columns land on an element in this edition's template"
    )
    template_dir = Path(TEMPLATES_DIR) / EDITION
    regenerated = generate_xml_string(
        [dict(r) for r in records.rows],
        EDITION,
        str(template_dir / "template.xml"),
        str(template_dir / f"{EDITION}.xsd"),
    )
    assert "<Nm>Bramley and Co Solicitors Client Account</Nm>" in regenerated
    uk = to_records(get_file("gb.fps.single", EDITION), EDITION)
    assert "debtor_account_IBAN" in uk.missing_required
    print(
        "  regenerated through the CSV pipeline; a Faster Payments file cannot "
        f"be (missing {', '.join(uk.missing_required)})"
    )


def main() -> None:
    """Run the four sections."""
    twin = _twin_and_back()
    _schema(twin)
    _edit_in_json()
    _records()
    print("Twins example completed.")


if __name__ == "__main__":
    main()
