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

"""``pain001 check``: run the validation ladder on existing files."""

from __future__ import annotations

import json
from pathlib import Path

import click

from pain001.check import CheckReport, check_document, format_text, to_sarif

#: Exit status when a file is refused before any rung runs.
EXIT_REFUSED = 2


class CheckRefused(click.ClickException):
    """A file or option check cannot run on (exit status 2)."""

    exit_code = EXIT_REFUSED


def _read_policy(rules: Path | None) -> str | None:
    """The policy text, capped as the policy engine caps it, or None."""
    if rules is None:
        return None
    try:
        from pain001.validation.policy import MAX_POLICY_BYTES
    except ImportError as exc:
        raise CheckRefused("--rules requires 'pain001[rules]'.") from exc
    with rules.open(encoding="utf-8") as handle:
        return handle.read(MAX_POLICY_BYTES + 1)


def _check_one(
    path: Path,
    scheme: str | None,
    policy: str | None,
    schematron: str | None,
) -> CheckReport:
    """Check one file; a file check cannot run on is refused (exit 2)."""
    try:
        return check_document(
            path.read_bytes(),
            scheme=scheme,
            policy=policy,
            schematron=schematron,
        )
    except (ValueError, UnicodeDecodeError, FileNotFoundError) as exc:
        raise CheckRefused(f"{path}: {exc}") from exc


def _render(checked: list[tuple[CheckReport, str]], output_format: str) -> str:
    """Every report in the chosen format."""
    if output_format == "json":
        return json.dumps(
            [{"file": name, **report.as_dict()} for report, name in checked],
            indent=2,
        )
    if output_format == "sarif":
        return json.dumps(to_sarif(checked), indent=2)
    return "\n".join(format_text(report, name) for report, name in checked)


@click.command("check")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--scheme",
    default=None,
    help="Scheme profiles to apply, comma-separated (e.g. sepa-sct).",
)
@click.option(
    "--rules",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Private YAML CEL policy file (needs pain001[rules]).",
)
@click.option(
    "--schematron",
    default=None,
    help="Schematron rulebook: sepa, fednow, cbpr, or a .sch path.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "sarif"]),
    default="text",
    show_default=True,
    help="Report format; sarif is for code-scanning uploads.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the report to this file instead of standard output.",
)
def check_cmd(
    files: tuple[Path, ...],
    scheme: str | None,
    rules: Path | None,
    schematron: str | None,
    output_format: str,
    output: Path | None,
) -> None:
    """Check existing pain.001 or pain.008 files (exit 0 = all pass).

    Runs the XSD of the message type the file declares, the message
    definition's cross-element rules (as the corpus build does), and
    any scheme profiles, policy or Schematron rulebook asked for.
    Exit 1 when a file has an error finding, 2 when a file or option
    cannot be checked.
    \f
    Args:
        files: The files to check.
        scheme: Scheme profiles, comma-separated.
        rules: Private CEL policy file.
        schematron: Schematron preset or path.
        output_format: ``text``, ``json`` or ``sarif``.
        output: Optional report file.

    A file that is not a bundled pain.001 or pain.008 message, or an
    option naming an unknown scheme or rulebook, is refused with
    :class:`CheckRefused` (exit 2) before any report is written.

    Raises:
        SystemExit: 1 when any file has an error finding.
    """
    policy = _read_policy(rules)
    checked = [
        (_check_one(path, scheme, policy, schematron), str(path))
        for path in files
    ]
    rendered = _render(checked, output_format)
    if output is None:
        click.echo(rendered)
    else:
        output.write_text(rendered + "\n", encoding="utf-8")
        click.echo(f"Wrote {output_format} report to {output}", err=True)
    if not all(report.passed for report, _ in checked):
        raise SystemExit(1)
