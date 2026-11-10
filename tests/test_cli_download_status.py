# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``pain001 download`` and ``pain001 status`` from the command line."""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass, field
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


def test_a_camt053_statement_is_summarised(tmp_path, monkeypatch):
    """Without camt053 installed, the core's own camt.053 parser reads it."""
    monkeypatch.setitem(sys.modules, "camt053", None)
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
            'pacs.008.001.08"/>',
            "pacs.008.001.08 is not supported",
        ),
        ("<not-xml", "cannot read"),
        ("<Document/>", "not a pain.002 or camt.05x"),
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


CAMT = '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:{}"/>'


class _FakeParseError(Exception):
    """Stands in for camt053.StatementParseError."""


@dataclass
class _Statement:
    entries: list[object] = field(default_factory=list)


@dataclass
class _Parsed:
    message_type: str
    statements: list[_Statement]


def _fake_camt053(monkeypatch, seen: list[str]) -> None:
    """Install a camt053 stand-in whose parse_document records its input."""

    def parse_document(xml: str) -> _Parsed:
        seen.append(xml)
        if "broken" in xml:
            raise _FakeParseError("Unrecognised container")
        kind = xml.split("xsd:")[1][:8]
        return _Parsed(kind, [_Statement([1, 2]), _Statement([3])])

    module = types.ModuleType("camt053")
    module.parse_document = parse_document  # type: ignore[attr-defined]
    module.StatementParseError = _FakeParseError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "camt053", module)


@pytest.mark.parametrize(
    "version", ["camt.052.001.08", "camt.053.001.08", "camt.054.001.08"]
)
def test_camt053_reads_every_camt_report_when_installed(
    tmp_path, monkeypatch, version
):
    """Plan D6: camt053 parses camt.052, .053 and .054 for status."""
    seen: list[str] = []
    _fake_camt053(monkeypatch, seen)
    path = tmp_path / "camt.xml"
    path.write_text(CAMT.format(version), encoding="utf-8")
    result = _status(str(path))
    assert result.exit_code == 0, result.output
    assert f"{path}: {version[:8]} 2 statements, 3 entries" in result.output
    assert seen == [CAMT.format(version)]


@pytest.mark.parametrize("version", ["camt.052.001.08", "camt.054.001.08"])
def test_camt052_and_054_need_camt053(tmp_path, monkeypatch, version):
    """Without camt053, only camt.053 is read; the others name the fix."""
    monkeypatch.setitem(sys.modules, "camt053", None)
    path = tmp_path / "camt.xml"
    path.write_text(CAMT.format(version), encoding="utf-8")
    result = _status(str(path))
    assert result.exit_code == 2
    assert (
        f"{version} needs camt053: pip install 'pain001[camt]'"
        in result.output
    )


def test_a_camt_file_camt053_cannot_parse_exits_2(tmp_path, monkeypatch):
    _fake_camt053(monkeypatch, [])
    path = tmp_path / "camt.xml"
    path.write_text(
        CAMT.format("camt.054.001.08").replace("/>", "><broken/></Document>"),
        encoding="utf-8",
    )
    result = _status(str(path))
    assert result.exit_code == 2
    assert "cannot read it: Unrecognised container" in result.output


@pytest.mark.parametrize("kind", ["pain.002", "camt.053"])
def test_status_reads_a_named_file_outside_the_working_directory(
    tmp_path, monkeypatch, kind
):
    """``download --to DIR`` saves anywhere; status must read it there.

    The parsers' path guard allows only the cwd and temp directories
    unless told a base; the file named on the command line is the base.
    """
    monkeypatch.setitem(sys.modules, "camt053", None)
    inbox, elsewhere = tmp_path / "inbox", tmp_path / "elsewhere"
    inbox.mkdir()
    elsewhere.mkdir()
    if kind == "pain.002":
        path = inbox / "reply.xml"
        path.write_bytes(FIXTURE.read_bytes())
    else:
        path = inbox / "stmt.xml"
        path.write_text(
            build_camt053_statement(
                "STMT-1",
                IBAN,
                "GBP",
                [{"amount": "10.00", "credit_debit_indicator": "DBIT"}],
            ),
            encoding="utf-8",
        )
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr("tempfile.tempdir", str(elsewhere))
    # The test base sits inside the package directory, itself an allowed
    # base; move that base away so only the file's own directory counts.
    monkeypatch.setattr(
        "pain001.security.path_validator.__file__",
        str(elsewhere / "pain001" / "security" / "path_validator.py"),
    )
    result = _status(str(path))
    assert "outside allowed directories" not in result.output
    assert f"{path}: {kind}" in result.output


def test_base_dir_confines_the_parsers(tmp_path):
    """``base_dir`` narrows the guard; a file outside it is refused."""
    from pain001.camt053 import parse_camt053_statement
    from pain001.exceptions import DataSourceError
    from pain001.pain002 import parse_pain002_report

    inside, outside = tmp_path / "in", tmp_path / "out"
    inside.mkdir()
    outside.mkdir()
    reply = outside / "reply.xml"
    reply.write_bytes(FIXTURE.read_bytes())
    stmt = outside / "stmt.xml"
    stmt.write_text(
        build_camt053_statement("S-1", IBAN, "GBP", []), encoding="utf-8"
    )
    with pytest.raises(DataSourceError, match="escapes base directory"):
        parse_pain002_report(str(reply), base_dir=inside)
    with pytest.raises(DataSourceError, match="escapes base directory"):
        parse_camt053_statement(str(stmt), base_dir=inside)
    assert parse_pain002_report(str(reply), base_dir=outside)["group_status"]


def _block_report(tmp_path: Path, txs: list[str], *, group: str) -> Path:
    """One payment block in ``group`` status holding ``txs`` transactions."""
    path = tmp_path / "block.xml"
    path.write_text(
        build_pain002_report(
            "STS-3",
            "MSG-3",
            group,
            [
                {
                    "original_payment_information_id": "PMT-3",
                    "payment_information_status": group,
                    "transactions": [
                        {
                            "original_end_to_end_id": f"E2E-{n}",
                            "transaction_status": tx,
                        }
                        for n, tx in enumerate(txs, 1)
                    ],
                }
            ],
            creation_datetime="2026-11-10T10:00:00",
        ),
        encoding="utf-8",
    )
    return path


def test_rejected_counts_transactions_not_lines(tmp_path):
    """A rejected group and block do not inflate the transaction count.

    0.0.85 printed "5 transactions, 11 rejected" for a mock bank reply:
    the group line and every block line were counted with the
    transactions.
    """
    path = _block_report(tmp_path, ["RJCT", "RJCT", "ACCP"], group="RJCT")
    result = _status(str(path))
    assert result.exit_code == 3
    head = result.output.splitlines()[0]
    assert head == (
        f"{path}: pain.002 RJCT, 3 transactions, 2 rejected; "
        "group and 1 payment block rejected"
    )
    assert "  RJCT E2E-1" in result.output and "  RJCT E2E-2" in result.output


def test_json_reports_the_rejected_transaction_count(tmp_path):
    path = _block_report(tmp_path, ["RJCT", "ACCP"], group="PART")
    result = _status("--format", "json", str(path))
    (entry,) = json.loads(result.output)
    assert entry["counts"] == {
        "transactions": 2,
        "rejected_transactions": 1,
        "rejected_groups": 0,
        "rejected_blocks": 0,
    }
    assert entry["validated"] is True


def test_json_counts_rejected_groups_and_blocks(tmp_path):
    """The group and block rejections are counts, not parsed text."""
    path = _block_report(tmp_path, ["RJCT"], group="RJCT")
    (entry,) = json.loads(_status("--format", "json", str(path)).output)
    assert entry["counts"]["rejected_groups"] == 1
    assert entry["counts"]["rejected_blocks"] == 1


def test_the_text_is_built_from_the_counts():
    """A rejected item's wording never decides what level it counts as."""
    from pain001.cli._status import Summary, _line  # noqa: PLC0415

    summary = Summary(
        "r.xml",
        "pain.002",
        "PART",
        {
            "transactions": 1,
            "rejected_transactions": 1,
            "rejected_groups": 0,
            "rejected_blocks": 0,
        },
        ["group payment E2E-1"],
        validated=True,
    )
    assert _line(summary).splitlines()[0] == (
        "r.xml: pain.002 PART, 1 transaction, 1 rejected"
    )


def test_a_reply_that_fails_its_bundled_schema_exits_2(tmp_path):
    """A pain.002 in a bundled version is validated before it is read."""
    path = _report(tmp_path, "bad.xml", "ACCP", "ACCP")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "<TxSts>ACCP</TxSts>", "<TxSts>NOPE</TxSts>"
        ),
        encoding="utf-8",
    )
    result = _status(str(path))
    assert result.exit_code == 2
    assert "failed validation" in result.output


def test_an_unbundled_version_is_read_but_reported_unvalidated(tmp_path):
    """No bundled schema: the reply is read and says it was not validated."""
    path = _report(tmp_path, "v10.xml", "ACCP", "ACCP")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "pain.002.001.03", "pain.002.001.10"
        ),
        encoding="utf-8",
    )
    result = _status(str(path))
    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0] == (
        f"{path}: pain.002 ACCP, 1 transaction, 0 rejected; "
        "not schema-validated (no bundled schema for pain.002.001.10)"
    )
    (entry,) = json.loads(_status("--format", "json", str(path)).output)
    assert entry["validated"] is False


def test_a_rejected_group_without_transactions_says_so(tmp_path):
    path = _block_report(tmp_path, [], group="RJCT")
    head = _status(str(path)).output.splitlines()[0]
    assert head.endswith(
        "0 transactions, 0 rejected; group and 1 payment block rejected"
    )
