# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``pain001 download`` and ``pain001 status`` from the command line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from pain001.camt053 import build_camt053_statement
from pain001.cli.cli import cli
from pain001.pain002 import build_pain002_report

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "pain001/test_fixtures/pain002_v15_sample.xml"
)
IBAN = "GB33BUKB20201555555555"


def _status(*args: str):
    return CliRunner().invoke(cli, ["status", *args])


def _report(tmp_path: Path, name: str, group: str, tx: str) -> Path:
    path = tmp_path / name
    path.write_text(
        build_pain002_report(
            "STS-1",
            "MSG-1",
            group,
            [
                {
                    "original_payment_information_id": "PMT-1",
                    "payment_information_status": group,
                    "original_end_to_end_id": "E2E-1",
                    "transaction_status": tx,
                    "status_reason": "AC04" if tx == "RJCT" else "",
                }
            ],
            creation_datetime="2026-11-09T10:00:00",
        ),
        encoding="utf-8",
    )
    return path


def test_an_accepted_report_exits_0(tmp_path):
    path = _report(tmp_path, "ok.xml", "ACCP", "ACCP")
    result = _status(str(path))
    assert result.exit_code == 0, result.output
    assert f"{path}: pain.002 ACCP, 1 transaction, 0 rejected" in result.output


def test_any_rejection_exits_3_and_names_it(tmp_path):
    ok = _report(tmp_path, "ok.xml", "ACCP", "ACCP")
    result = _status(str(ok), str(FIXTURE))
    assert result.exit_code == 3
    assert "pain.002 PART, 1 transaction, 1 rejected" in result.output
    assert "  RJCT PaymentID6789 AC04" in result.output


def test_a_rejected_group_counts_without_transactions(tmp_path):
    path = tmp_path / "group.xml"
    path.write_text(
        build_pain002_report(
            "STS-2",
            "MSG-2",
            "RJCT",
            [
                {
                    "original_payment_information_id": "PMT-2",
                    "payment_information_status": "RJCT",
                }
            ],
            creation_datetime="2026-11-09T10:00:00",
        ),
        encoding="utf-8",
    )
    result = _status("--format", "json", str(path))
    assert result.exit_code == 3
    (entry,) = json.loads(result.output)
    assert entry["rejected"] == ["group MSG-2", "payment PMT-2"]


def test_a_camt053_statement_is_summarised(tmp_path):
    path = tmp_path / "stmt.xml"
    path.write_text(
        build_camt053_statement(
            "STMT-1",
            IBAN,
            "GBP",
            [{"amount": "10.00", "credit_debit_indicator": "DBIT"}],
        ),
        encoding="utf-8",
    )
    result = _status(str(path))
    assert result.exit_code == 0
    assert f"{path}: camt.053 1 statement, 1 entry" in result.output


@pytest.mark.parametrize(
    "body, message",
    [
        (
            '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:'
            'camt.054.001.08"/>',
            "camt.054.001.08 is not supported",
        ),
        ("<not-xml", "cannot read"),
        ("<Document/>", "not a pain.002 or camt.053"),
    ],
)
def test_an_unreadable_or_unsupported_file_exits_2(tmp_path, body, message):
    path = tmp_path / "x.xml"
    path.write_text(body, encoding="utf-8")
    result = _status(str(path))
    assert result.exit_code == 2
    assert message in result.output


def test_download_prints_what_it_saved(tmp_path, monkeypatch):
    """The command reads secrets from the environment and reports."""
    pytest.importorskip("paramiko")
    from pain001.transport import download

    seen = {}

    def fake(url, to_dir, **kwargs):
        seen.update(kwargs, url=url, to_dir=to_dir)
        return download.DownloadResult(
            (
                download.Fetched(
                    "/outbox/a.xml", f"{to_dir}/a.xml", "ab" * 32, 3, "saved"
                ),
                download.Fetched(
                    "/outbox/b.xml", f"{to_dir}/b.xml", "cd" * 32, 4, "known"
                ),
            ),
            ("link.xml",),
            2,
        )

    monkeypatch.setattr(download, "download_sftp", fake)
    monkeypatch.setenv("BANK_PW", "test-only")
    result = CliRunner().invoke(
        cli,
        [
            "download",
            "--sftp",
            "sftp://ops@h/outbox/",
            "--to",
            str(tmp_path),
            "--pattern",
            "*.xml",
            "--after-fetch",
            "move:/archive",
            "--settle-seconds",
            "5",
            "--max-files",
            "10",
            "--max-bytes",
            "1000",
            "--password-env",
            "BANK_PW",
        ],
    )
    assert result.exit_code == 0, result.output
    assert f"Saved: /outbox/a.xml -> {tmp_path}/a.xml" in result.output
    assert "Known: /outbox/b.xml" in result.output
    assert "Skipped: link.xml" in result.output
    assert "2 left for the next run" in result.output
    policy = seen["policy"]
    assert (policy.pattern, policy.after_fetch) == ("*.xml", "move:/archive")
    assert (policy.settle_seconds, policy.max_files) == (5, 10)
    assert seen["password"] == "test-only"
    assert "test-only" not in result.output


def test_download_reports_failures_without_a_traceback(tmp_path, monkeypatch):
    pytest.importorskip("paramiko")
    from pain001.transport import download

    def fails(*args, **kwargs):
        raise ValueError("Download from a directory URL ending in '/'.")

    monkeypatch.setattr(download, "download_sftp", fails)
    result = CliRunner().invoke(
        cli, ["download", "--sftp", "sftp://ops@h/x", "--to", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "directory URL" in result.output


def test_download_without_the_extra_names_it(monkeypatch, tmp_path):
    """Without paramiko the transport cannot import; the command says why."""
    import sys

    monkeypatch.setitem(sys.modules, "pain001.transport.download", None)
    result = CliRunner().invoke(
        cli, ["download", "--sftp", "sftp://ops@h/x/", "--to", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "pain001[upload]" in result.output


def test_a_pain002_namespace_without_a_report_exits_2(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text(
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:'
        'pain.002.001.10"><Other/></Document>',
        encoding="utf-8",
    )
    result = _status(str(path))
    assert result.exit_code == 2
    assert "not a pain.002 payment status report" in result.output


def test_download_with_nothing_left_says_nothing_extra(tmp_path, monkeypatch):
    pytest.importorskip("paramiko")
    from pain001.transport import download

    monkeypatch.setattr(
        download,
        "download_sftp",
        lambda *a, **k: download.DownloadResult(()),
    )
    result = CliRunner().invoke(
        cli, ["download", "--sftp", "sftp://ops@h/o/", "--to", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert result.output == ""
