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

"""Check payment files that already exist, from Python and the CLI.

``check_document`` runs the validation ladder on a pain.001 or pain.008
document pain001 did not necessarily write: the XSD of the message type
its namespace names, the message definition's cross-element rules, and
any scheme profiles asked for. ``pain001 check`` runs the same engine
and exits 0 when every file passes, 1 when one has an error finding and
2 when a file cannot be checked.

Run from the repository root::

    python examples/27_check_existing_file.py
"""

import json
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from pain001 import CheckReport, check_document
from pain001.constants import TEMPLATES_DIR

SAMPLE = TEMPLATES_DIR / "pain.001.001.09" / "pain.001.001.09.xml"


def show(report: CheckReport, name: str) -> None:
    """Print one report's verdict and its first findings."""
    verdict = "passed" if report.passed else "failed"
    print(f"{name}: {report.message_type} {verdict} {report.rungs}")
    for finding in report.findings[:3]:
        print(f"  {finding.severity} {finding.rung}/{finding.rule}")


def main() -> None:
    """Check a bundled sample, a broken copy, and both from the CLI."""
    xml = SAMPLE.read_text(encoding="utf-8")
    show(check_document(xml), "sample")
    show(check_document(xml, scheme="sepa-sct"), "sample under sepa-sct")

    broken = xml.replace("<NbOfTxs>", "<Unknown/><NbOfTxs>", 1)
    report = check_document(broken)
    show(report, "broken copy")
    assert not report.passed

    with tempfile.TemporaryDirectory() as workdir:
        bad = Path(workdir) / "broken.xml"
        bad.write_text(broken, encoding="utf-8")
        result = subprocess.run(  # nosec B603
            [
                sys.executable,
                "-m",
                "pain001",
                "check",
                "--format",
                "json",
                str(SAMPLE),
                str(bad),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    verdicts = [entry["passed"] for entry in json.loads(result.stdout)]
    print(f"pain001 check -> exit {result.returncode}, passed {verdicts}")
    assert result.returncode == 1
    assert verdicts == [True, False]


if __name__ == "__main__":
    main()
