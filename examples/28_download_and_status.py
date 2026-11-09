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

"""Read a bank's replies with ``pain001 status``; ``download`` refusals.

``pain001 status`` reads pain.002 reports and camt.053 statements and
exits 3 when anything was rejected, so a scheduled job can alert.
``pain001 download`` fetches replies over SFTP exactly once; here it is
shown refusing bad input before it opens any connection. The loopback
round trip is in ``tests/test_sftp_download.py``.

Run from the repository root::

    python examples/28_download_and_status.py
"""

import json
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from pain001.pain002 import build_pain002_report


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the pain001 CLI and return its result."""
    return subprocess.run(  # nosec B603
        [sys.executable, "-m", "pain001", *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def write_report(path: Path, tx_status: str) -> None:
    """Write a synthetic pain.002 with one transaction in ``tx_status``."""
    path.write_text(
        build_pain002_report(
            "STS-1",
            "MSG-1",
            "PART" if tx_status == "RJCT" else "ACCP",
            [
                {
                    "original_payment_information_id": "PMT-1",
                    "payment_information_status": "ACCP",
                    "original_end_to_end_id": "E2E-1",
                    "transaction_status": tx_status,
                    "status_reason": "AC04" if tx_status == "RJCT" else "",
                }
            ],
            creation_datetime="2026-11-09T10:00:00",
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Report an accepted and a rejected reply, then download refusals."""
    with tempfile.TemporaryDirectory() as workdir:
        accepted, rejected = Path(workdir, "ok.xml"), Path(workdir, "no.xml")
        write_report(accepted, "ACCP")
        write_report(rejected, "RJCT")
        result = run("status", str(accepted), str(rejected))
        print(result.stdout.strip())
        print(f"pain001 status -> exit {result.returncode}")
        assert result.returncode == 3
        result = run("status", "--format", "json", str(accepted))
        print(f"json: {json.loads(result.stdout)[0]['group_status']}")
        assert result.returncode == 0

        result = run("download", "--help")
        assert result.returncode == 0 and "--after-fetch" in result.stdout
        print("pain001 download --help -> exit 0")
        for args, needle in [
            (
                ["--sftp", "sftp://ops@bank.example/outbox", "--to", workdir],
                "directory URL",
            ),
            (
                [
                    "--sftp",
                    "sftp://ops@bank.example/outbox/",
                    "--to",
                    workdir,
                    "--after-fetch",
                    "copy",
                ],
                "--after-fetch",
            ),
        ]:
            result = run("download", *args)
            message = result.stderr + result.stdout
            print(f"download refusal -> exit {result.returncode}")
            assert result.returncode != 0
            assert needle in message or "pain001[upload]" in message


if __name__ == "__main__":
    main()
