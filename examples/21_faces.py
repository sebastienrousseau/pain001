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

"""Faces: one pain.001 payment in another standard's JSON (ADR-0005).

1. Generate a one-transaction pain.001.001.03 from the sample CSV.
2. Project it to each face: UK Open Banking v4.0.1, Berlin Group
   NextGenPSD2 v1.3.16 and ISO 20022 names in snake_case, and read the
   loss report of every source element a face does not carry.
3. A refusal: the same row as pain.001.001.09 has no ``InstrId``, which
   UK Open Banking requires, so the face raises ``FaceError`` instead
   of inventing one.
4. ``pain001 face`` on the command line: a payload, a loss report on
   standard error, and exit code 1 for a refused document.

Run from the repository root::

    python examples/21_faces.py
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from pain001 import generate_xml_string
from pain001.constants import TEMPLATES_DIR
from pain001.csv.load_csv_data import load_csv_data
from pain001.faces import (
    FaceError,
    available_faces,
    list_supported_faces,
    project_face,
)

DATA_FILE = Path(__file__).resolve().parent / "data" / "payments.csv"
CONSENT_ID = "consent-example-0001"  # a placeholder, not a real consent


def _generate(edition: str) -> str:
    """1. The first CSV row as a single-transaction pain.001 document."""
    row = dict(load_csv_data(str(DATA_FILE))[0])
    row.update(nb_of_txs="1", ctrl_sum=row["payment_amount"])
    template_dir = TEMPLATES_DIR / edition
    return generate_xml_string(
        [row],
        edition,
        str(template_dir / "template.xml"),
        str(template_dir / f"{edition}.xsd"),
    )


def _uk_open_banking(xml: str) -> None:
    """2a. A domestic payment; a ConsentId binding makes it a submission."""
    consent = project_face(xml, "uk_open_banking")
    initiation = consent.payload["Data"]["Initiation"]
    assert initiation["InstructedAmount"]["Currency"] == "EUR"
    assert "ConsentId" not in consent.payload["Data"]
    submission = project_face(
        xml, "uk_open_banking", bindings={"ConsentId": CONSENT_ID}
    )
    assert submission.payload["Data"]["ConsentId"] == CONSENT_ID
    report = consent.loss_report
    print(
        f"uk_open_banking: {initiation['InstructedAmount']['Amount']} "
        f"{initiation['InstructedAmount']['Currency']} to "
        f"{initiation['CreditorAccount']['Name']}; carried "
        f"{len(report.mapped_paths)} of {report.total_source_elements} "
        "source elements"
    )


def _berlin_group(xml: str) -> None:
    """2b. A single payment initiation body."""
    result = project_face(xml, "berlin_group")
    payload = result.payload
    assert payload["instructedAmount"]["currency"] == "EUR"
    assert payload["creditorAccount"] == {"iban": "DE36210501700024690959"}
    report = result.loss_report
    assert not report.is_lossless
    print(
        f"berlin_group: {len(payload)} top-level fields; "
        f"{report.loss_ratio:.0%} of the source not carried, e.g. "
        f"{report.unmapped_paths[0]}"
    )


def _iso_2018(xml: str) -> None:
    """2c. Full ISO names; .03's BIC has no 2018 name, so it is a loss."""
    result = project_face(xml, "iso_2018")
    assert list(result.payload) == ["group_header", "payment_information"]
    report = result.loss_report.to_dict()
    partitioned = report["mapped_count"] + report["unmapped_count"]
    assert partitioned == report["total_source_elements"]
    assert all(p.endswith("/BIC") for p in report["unmapped_paths"])
    print(
        f"iso_2018: {report['mapped_count']} of "
        f"{report['total_source_elements']} carried; the "
        f"{report['unmapped_count']} not carried are .03 BIC elements, "
        "which have no ISO 2018 name"
    )


def _refusal(xml_09: str) -> None:
    """3. A face refuses a document that lacks what the target needs."""
    refusal = None
    try:
        project_face(xml_09, "uk_open_banking")
    except FaceError as exc:
        refusal = str(exc)
    assert refusal and "PmtId/InstrId is required" in refusal, refusal
    print(f"refused: FaceError: {refusal}")
    assert project_face(xml_09, "berlin_group").payload, "BG needs no InstrId"


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the pain001 CLI in a subprocess and return the result.

    Args:
        args: CLI arguments to append after ``python -m pain001``.
        cwd: Working directory for the subprocess.

    Returns:
        The completed process with captured output.
    """
    return subprocess.run(  # nosec B603
        [sys.executable, "-m", "pain001", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _cli(xml_03: str, xml_09: str) -> None:
    """4. ``pain001 face`` with bindings, an output file and a refusal."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "pay03.xml").write_text(xml_03, encoding="utf-8")
        (work / "pay09.xml").write_text(xml_09, encoding="utf-8")
        bindings = work / "bindings.json"  # private: keep out of git
        bindings.write_text(json.dumps({"ConsentId": CONSENT_ID}))
        ok = run_cli(
            ["face", "pay03.xml", "--face", "uk_open_banking"]
            + ["--bindings", "bindings.json", "-o", "out.json"]
            + ["--loss-report"],
            work,
        )
        assert ok.returncode == 0, ok.stderr
        assert "Face Loss Report:" in ok.stderr
        out = json.loads((work / "out.json").read_text(encoding="utf-8"))
        assert out["Data"]["ConsentId"] == CONSENT_ID
        refused = run_cli(["face", "pay09.xml"], work)
        assert refused.returncode == 1
        assert "Face projection error" in refused.stderr
    summary = next(
        line.strip()
        for line in ok.stderr.splitlines()
        if line.strip().startswith("mapped")
    )
    print(
        f"cli: exit {ok.returncode} ({summary}); "
        f"refused document exits {refused.returncode}"
    )


def main() -> int:
    """Run the four sections."""
    assert available_faces() == [f["name"] for f in list_supported_faces()]
    print(f"faces: {', '.join(available_faces())}")
    xml_03 = _generate("pain.001.001.03")
    xml_09 = _generate("pain.001.001.09")
    _uk_open_banking(xml_03)
    _berlin_group(xml_03)
    _iso_2018(xml_03)
    _refusal(xml_09)
    _cli(xml_03, xml_09)
    print("Faces example completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
