# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parse the messages your bank sends back: pain.002 and camt.053.

After you submit a pain.001, banks reply with a pain.002 payment status
report and an end-of-day camt.053 statement. Pain001 reads both into
plain Python structures so you can reconcile programmatically.

Run from the repository root::

    python examples/07_parse_bank_responses.py
"""

from pathlib import Path

from pain001 import parse_camt053_statement, parse_pain002_report

FIXTURES = Path("pain001/test_fixtures")


def main() -> None:
    """Parse a sample pain.002 status report and a camt.053 statement."""
    status = parse_pain002_report(str(FIXTURES / "pain002_sample.xml"))
    assert isinstance(status, dict) and status
    print("pain.002 status report parsed:")
    for key in list(status)[:5]:
        print(f"  {key}: {status[key]!r}")

    statement = parse_camt053_statement(str(FIXTURES / "camt053_sample.xml"))
    assert isinstance(statement, dict) and statement
    print("camt.053 statement parsed:")
    for key in list(statement)[:5]:
        print(f"  {key}: {statement[key]!r}")

    print("Bank-response parsing example completed.")


if __name__ == "__main__":
    main()
