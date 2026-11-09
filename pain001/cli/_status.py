# SPDX-License-Identifier: Apache-2.0 OR MIT
"""``pain001 status``: what a bank said about your payments.

Reads pain.002 status reports and camt.053 statements with the core's
own parsers and exits 3 when any group, payment block or transaction
was rejected (``RJCT``), so a scheduled job can alert on it. Exit 2
means a file could not be read or is a message this command does not
cover yet.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import click
from defusedxml import ElementTree as defused_et
from defusedxml.ElementTree import ParseError

from pain001.exceptions import DataSourceError, SchemaValidationError

EXIT_REJECTED = 3
_MESSAGE = re.compile(
    r"\{urn:iso:std:iso:20022:tech:xsd:(([a-z]+\.\d{3})\.\d{3}\.\d{2})\}"
)
_COVERED = ("pain.002", "camt.053")


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


def _plural(count: int, one: str, many: str) -> str:
    """``1 transaction`` or ``2 transactions``."""
    return f"{count} {one if count == 1 else many}"


def _message_of(path: Path) -> str:
    """Return ``pain.002`` or ``camt.053`` from the root element.

    Args:
        path: The file to inspect.

    Returns:
        The message family its namespace names.

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
        raise StatusRefused(f"{path}: not a pain.002 or camt.053 message.")
    if match[2] not in _COVERED:
        raise StatusRefused(
            f"{path}: {match[1]} is not supported; "
            "status reads pain.002 and camt.053."
        )
    return match[2]


def _pain002(path: Path) -> Summary:
    """Summarise a pain.002, listing every rejected level."""
    from pain001.pain002 import parse_pain002_report  # noqa: PLC0415

    report: dict[str, Any] = parse_pain002_report(str(path))
    rejected = []
    if report["group_status"] == "RJCT":
        rejected.append(f"group {report['original_message_id']}")
    transactions = 0
    for block in report["payment_statuses"]:
        if block["payment_information_status"] == "RJCT":
            rejected.append(
                f"payment {block['original_payment_information_id']}"
            )
        for tx in block["transactions"]:
            transactions += 1
            if tx["transaction_status"] == "RJCT":
                rejected.append(
                    f"RJCT {tx['original_end_to_end_id']} {tx['status_reason']}".strip()
                )
    return Summary(
        str(path),
        "pain.002",
        report["group_status"],
        {"transactions": transactions},
        rejected,
    )


def _camt053(path: Path) -> Summary:
    """Summarise a camt.053: statements and entries, nothing rejected."""
    from pain001.camt053 import parse_camt053_statement  # noqa: PLC0415

    statements: list[dict[str, Any]] = parse_camt053_statement(str(path))[
        "statements"
    ]  # type: ignore[assignment]
    entries = sum(len(s["entries"]) for s in statements)
    return Summary(
        str(path),
        "camt.053",
        counts={"statements": len(statements), "entries": entries},
    )


def summarise(path: Path) -> Summary:
    """Read one status file.

    Args:
        path: A pain.002 report or camt.053 statement.

    Returns:
        Its message type, counts and rejected items.

    Raises:
        StatusRefused: If the file is unreadable or not covered.
    """
    message = _message_of(path)
    try:
        return _pain002(path) if message == "pain.002" else _camt053(path)
    except (DataSourceError, SchemaValidationError) as exc:
        raise StatusRefused(f"{path}: cannot read it: {exc}") from exc


def _line(summary: Summary) -> str:
    """The text report for one file."""
    if summary.message == "camt.053":
        counts = summary.counts
        return (
            f"{summary.file}: camt.053 "
            f"{_plural(counts['statements'], 'statement', 'statements')}, "
            f"{_plural(counts['entries'], 'entry', 'entries')}"
        )
    head = (
        f"{summary.file}: pain.002 {summary.group_status}, "
        f"{_plural(summary.counts['transactions'], 'transaction', 'transactions')}, "
        f"{len(summary.rejected)} rejected"
    )
    return "\n".join([head, *(f"  {item}" for item in summary.rejected)])


@click.command("status")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def status_cmd(files: tuple[Path, ...], output_format: str) -> None:
    """Report the status in pain.002 and camt.053 FILES (exit 3 on RJCT).

    Exit 0 when nothing was rejected, 3 when any group, payment block or
    transaction was, and 2 when a file cannot be read.
    \f
    Args:
        files: pain.002 reports and camt.053 statements.
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
