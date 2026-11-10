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

"""Check payment files against a private bank profile, in-house.

A bank's usage guideline adds constraints to the ISO schema. A team
turns them into two files kept inside its own network: a CEL policy for
record-level rules (``rules.yaml``, ``pain001[rules]``) and a Schematron
rulebook for document-level rules (``profile.sch``). ``check_document``
and ``pain001 check`` apply both after the XSD and message-definition
checks. Nothing is sent anywhere. The template here is for a fictional
"Example Bank"; see ``docs/bank-profiles.md``.

Run from the repository root::

    python examples/29_private_bank_profile.py
"""

from pathlib import Path

from pain001 import CheckReport, check_document
from pain001.constants import TEMPLATES_DIR

PROFILE = Path(__file__).resolve().parent / "bank-profile"
SAMPLE = TEMPLATES_DIR / "pain.001.001.09" / "pain.001.001.09.xml"


def check(xml: str) -> CheckReport:
    """Check one document against the Example Bank profile."""
    return check_document(
        xml,
        policy=(PROFILE / "rules.yaml").read_text(encoding="utf-8"),
        schematron=str(PROFILE / "profile.sch"),
    )


def show(report: CheckReport, name: str) -> None:
    """Print the verdict and the rule ids that fired."""
    verdict = "passed" if report.passed else "failed"
    rules = sorted({f"{f.severity}:{f.rule}" for f in report.findings})
    print(f"{name}: {verdict} {report.rungs} {rules}")


def main() -> None:
    """The sample passes; a copy that breaks the profile fails."""
    xml = SAMPLE.read_text(encoding="utf-8")
    report = check(xml)
    show(report, "sample")
    assert report.passed

    broken = xml.replace(
        '<InstdAmt Ccy="EUR">150.00</InstdAmt>',
        '<InstdAmt Ccy="EUR">75000.00</InstdAmt>',
        1,
    )
    report = check(broken)
    show(report, "75,000 EUR payment")
    assert not report.passed
    assert "EXB-LIMIT" in {f.rule for f in report.findings}


if __name__ == "__main__":
    main()
