# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``pain001 status``: what a bank said about your payments.

Reads pain.002 status reports with the core's parser, and camt.052,
camt.053 and camt.054 reports with the ``camt053`` package when it is
installed (plan decision D6: camt parsing belongs to camt053, not to a
second parser here). Without camt053, the core's own camt.053 parser
still reads camt.053, and camt.052 and camt.054 are refused with the
install command (``pip install 'pain001[camt]'``). It exits 3 when any
group, payment block or transaction was rejected (``RJCT``), so a
scheduled job can alert on it. Exit 2 means a file could not be read or is a message this command
does not cover.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import click
from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

from pain001.cli._format import format_option
from pain001.exceptions import DataSourceError, SchemaValidationError

EXIT_REJECTED = 3
_MESSAGE = re.compile(
    r"\{urn:iso:std:iso:20022:tech:xsd:(([a-z]+\.\d{3})\.\d{3}\.\d{2})\}"
)
_COVERED = ("pain.002", "camt.052", "camt.053", "camt.054")


class StatusRefused(click.ClickException):
    """A file could not be read or is not covered (exit status 2)."""

    exit_code = 2


@dataclass(frozen=True)
class Summary:
    """One file's status: what it is, its counts and what was rejected."""

    file: str
    message: str
    group_status: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    rejected: list[str] = field(default_factory=list)
    #: The full message version its namespace names.
    version: str = ""
    #: pain.002 only: whether it was checked against a bundled schema
    #: (``False`` for a version the package does not bundle).
    validated: bool | None = None


def _plural(count: int, one: str, many: str) -> str:
    """``1 transaction`` or ``2 transactions``."""
    return f"{count} {one if count == 1 else many}"


def _message_of(path: Path) -> tuple[str, str]:
    """Return the message family and full version from the root element.

    Args:
        path: The file to inspect.

    Returns:
        The family (``pain.002``, ``camt.053``) and the version its
        namespace names (``camt.053.001.08``).

    Raises:
        StatusRefused: Unreadable, or not a message this command reads.
    """
    try:
        root = defused_et.parse(path).getroot()
        tag = "" if root is None else str(root.tag)
    except (ParseError, OSError) as exc:
        raise StatusRefused(f"{path}: cannot read it: {exc}") from exc
    match = _MESSAGE.match(tag)
    if match is None:
        raise StatusRefused(f"{path}: not a pain.002 or camt.05x message.")
    if match[2] not in _COVERED:
        raise StatusRefused(
            f"{path}: {match[1]} is not supported; "
            "status reads pain.002, camt.052, camt.053 and camt.054."
        )
    return match[2], match[1]


def _pain002(path: Path, version: str) -> Summary:
    """Summarise a pain.002, listing every rejected level.

    A reply in a version with a bundled schema is validated against it
    first; any other version is read unvalidated and says so.

    Args:
        path: The pain.002 report.
        version: Its version, from the root namespace.

    Returns:
        Its group status, counts per level and rejected items.
    """
    from pain001.pain002 import (  # noqa: PLC0415
        bundled_schema_versions,
        parse_pain002_report,
    )

    validated = version in bundled_schema_versions()
    report: dict[str, Any] = parse_pain002_report(
        str(path), validate=validated, base_dir=path.parent
    )
    counts, rejected = _pain002_rejections(report)
    return Summary(
        str(path),
        "pain.002",
        report["group_status"],
        counts,
        rejected,
        version=version,
        validated=validated,
    )


def _pain002_rejections(
    report: dict[str, Any],
) -> tuple[dict[str, int], list[str]]:
    """Count a parsed pain.002 per level and name what was rejected.

    Args:
        report: :func:`~pain001.pain002.parse_pain002_report` output.

    Returns:
        The counts (transactions, and rejections per level) and the
        rejected items in document order.
    """
    counts = dict.fromkeys(
        (
            "transactions",
            "rejected_transactions",
            "rejected_groups",
            "rejected_blocks",
        ),
        0,
    )
    rejected = []
    if report["group_status"] == "RJCT":
        counts["rejected_groups"] = 1
        rejected.append(f"group {report['original_message_id']}")
    for block in report["payment_statuses"]:
        if block["payment_information_status"] == "RJCT":
            counts["rejected_blocks"] += 1
            rejected.append(
                f"payment {block['original_payment_information_id']}"
            )
        for tx in block["transactions"]:
            counts["transactions"] += 1
            if tx["transaction_status"] == "RJCT":
                counts["rejected_transactions"] += 1
                rejected.append(
                    f"RJCT {tx['original_end_to_end_id']} {tx['status_reason']}".strip()
                )
    return counts, rejected


def _camt_counts(
    path: Path, message: str, statements: int, entries: int
) -> Summary:
    """A camt summary: statements and entries, nothing rejected."""
    return Summary(
        str(path),
        message,
        counts={"statements": statements, "entries": entries},
    )


def _camt_with_camt053(path: Path, message: str, camt053: Any) -> Summary:
    """Summarise any camt.05x with the camt053 package (plan D6)."""
    try:
        parsed = camt053.parse_document(path.read_text(encoding="utf-8"))
    except camt053.StatementParseError as exc:
        raise StatusRefused(f"{path}: cannot read it: {exc}") from exc
    statements = parsed.statements
    entries = sum(len(s.entries) for s in statements)
    return _camt_counts(path, message, len(statements), entries)


def _camt053_module() -> Any | None:
    """The ``camt053`` package, or ``None`` when it is not installed."""
    try:
        import camt053  # type: ignore[import-not-found,unused-ignore]  # noqa: PLC0415
    except ImportError:
        return None
    return camt053


def _camt(path: Path, message: str, version: str) -> Summary:
    """Summarise a camt.05x, with camt053 when it is installed.

    Args:
        path: A camt.052, camt.053 or camt.054 file.
        message: Which of the three it is.
        version: Its full message version, for the refusal.

    Returns:
        Its statement and entry counts.

    Raises:
        StatusRefused: camt.052 or camt.054 without camt053 installed.
    """
    camt053 = _camt053_module()
    if camt053 is not None:
        return _camt_with_camt053(path, message, camt053)
    if message != "camt.053":
        raise StatusRefused(
            f"{path}: {version} needs camt053: pip install 'pain001[camt]'"
        )
    from pain001.camt053 import parse_camt053_statement  # noqa: PLC0415

    statements: list[dict[str, Any]] = parse_camt053_statement(
        str(path), base_dir=path.parent
    )["statements"]  # type: ignore[assignment]
    entries = sum(len(s["entries"]) for s in statements)
    return _camt_counts(path, message, len(statements), entries)


def summarise(path: Path) -> Summary:
    """Read one status file.

    Args:
        path: A pain.002 report or camt.052, camt.053 or camt.054 file.

    Returns:
        Its message type, counts and rejected items.

    Raises:
        StatusRefused: If the file is unreadable or not covered.
    """
    # The user named this file and Click checked it exists; resolving it
    # removes any ``..`` the path guard would refuse, and its directory
    # is the only base the parsers then allow.
    resolved = path.resolve()
    message, version = _message_of(resolved)
    try:
        if message == "pain.002":
            summary = _pain002(resolved, version)
        else:
            summary = _camt(resolved, message, version)
    except (DataSourceError, SchemaValidationError) as exc:
        raise StatusRefused(f"{path}: cannot read it: {exc}") from exc
    return replace(summary, file=str(path), version=version)


def _line(summary: Summary) -> str:
    """The text report for one file."""
    if summary.message.startswith("camt."):
        counts = summary.counts
        return (
            f"{summary.file}: {summary.message} "
            f"{_plural(counts['statements'], 'statement', 'statements')}, "
            f"{_plural(counts['entries'], 'entry', 'entries')}"
        )
    counts = summary.counts
    head = (
        f"{summary.file}: pain.002 {summary.group_status}, "
        f"{_plural(counts['transactions'], 'transaction', 'transactions')}, "
        f"{counts['rejected_transactions']} rejected"
        f"{_levels_rejected(counts)}"
    )
    if summary.validated is False:
        head += (
            f"; not schema-validated (no bundled schema for {summary.version})"
        )
    return "\n".join([head, *(f"  {item}" for item in summary.rejected)])


def _levels_rejected(counts: dict[str, int]) -> str:
    """Name the group and payment-block rejections, which are not counted.

    The count in the head is of transactions; a rejected group or payment
    block is named after it so a reader still sees why the exit is 3.

    Args:
        counts: The summary's counts, with ``rejected_groups`` and
            ``rejected_blocks``.

    Returns:
        ``"; group and 2 payment blocks rejected"`` or similar, or ``""``.
    """
    levels = []
    if counts["rejected_groups"]:
        levels.append("group")
    blocks = counts["rejected_blocks"]
    if blocks:
        levels.append(_plural(blocks, "payment block", "payment blocks"))
    return f"; {' and '.join(levels)} rejected" if levels else ""


@click.command("status")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@format_option()
def status_cmd(files: tuple[Path, ...], output_format: str) -> None:
    """Report the status in pain.002 and camt.05x FILES (exit 3 on RJCT).

    Exit 0 when nothing was rejected, 3 when any group, payment block or
    transaction was, and 2 when a file cannot be read.
    \f
    Args:
        files: pain.002 reports and camt.052, camt.053 or camt.054 files.
        output_format: ``text`` or ``json``.

    Raises:
        SystemExit: 3 when anything was rejected.
    """
    summaries = [summarise(path) for path in files]
    if output_format == "json":
        click.echo(json.dumps([asdict(s) for s in summaries], indent=2))
    else:
        click.echo("\n".join(_line(s) for s in summaries))
    if any(s.rejected for s in summaries):
        raise SystemExit(EXIT_REJECTED)
