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

"""``pain001 verify-signature``: check XML-DSig signatures on files.

Exit status 0 when every file verifies, 1 when any does not, 2 when the
command cannot run (no trust choice, an unreadable certificate, a
missing ``pain001[sign]``). Like ``verify_signature``, it needs the
signer's certificate (``--cert``) or an explicit
``--trust-embedded-cert``, which proves a file is unchanged but not who
signed it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from pain001.security._dsig_algorithms import ALGORITHMS

if TYPE_CHECKING:
    from pain001.security.dsig import SignatureReport

EXIT_REFUSED = 2


class VerifyRefused(click.ClickException):
    """The command cannot run (exit status 2)."""

    exit_code = EXIT_REFUSED


def xml_sign_alg_option(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    """Hand ``--xml-sign-alg`` to signing via ``PAIN001_XML_SIGN_ALG``.

    Args:
        ctx: The Click context (unused).
        param: The option (unused).
        value: The algorithm name, or ``None`` when the flag is absent.

    Returns:
        The value, unchanged.
    """
    if value is not None:
        os.environ["PAIN001_XML_SIGN_ALG"] = value
    return value


def xml_sign_options(command: Callable[..., Any]) -> Callable[..., Any]:
    """``generate``'s signing options, in the order ``--help`` lists them.

    ``--xml-sign-key``, ``--xml-sign-cert`` and
    ``--xml-sign-passphrase-env`` reach the command as parameters;
    ``--xml-sign-alg`` goes through ``PAIN001_XML_SIGN_ALG``, so the
    command's signature (already over the complexity ceilings) does not
    grow.

    Args:
        command: The Click command function.

    Returns:
        The command with the options attached.
    """
    options = [
        click.option(
            "--xml-sign-key",
            type=click.Path(exists=True, dir_okay=False, readable=True),
            default=None,
            help="Private key PEM file (RSA, or EC P-256/P-384) to sign "
            "the generated XML with W3C XML-DSig.",
        ),
        click.option(
            "--xml-sign-cert",
            type=click.Path(exists=True, dir_okay=False, readable=True),
            default=None,
            help="Optional X.509 certificate PEM file to embed in "
            "XML-DSig <KeyInfo>.",
        ),
        click.option(
            "--xml-sign-alg",
            type=click.Choice(sorted(ALGORITHMS)),
            expose_value=False,
            callback=xml_sign_alg_option,
            help="XML-DSig algorithm; default follows the key "
            "(RSA: rsa-sha256).",
        ),
        click.option(
            "--xml-sign-passphrase-env",
            type=str,
            default=None,
            metavar="VAR",
            help="Environment variable holding the passphrase for "
            "--xml-sign-key.",
        ),
    ]
    for option in reversed(options):
        command = option(command)
    return command


def _line(name: str, report: SignatureReport) -> str:
    """One line of the text report for one file."""
    if not report.valid:
        return f"{name}: invalid: {report.reason}"
    signer = f", signer {report.signer}" if report.signer else ""
    how = (
        "trusted certificate"
        if report.trust == "anchor"
        else "embedded certificate, integrity only"
    )
    return f"{name}: valid ({report.algorithm}, {how}{signer})"


@click.command("verify-signature")
@click.argument(
    "files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--cert",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="The signer's PEM certificate or PEM public key (trust anchor).",
)
@click.option(
    "--trust-embedded-cert",
    is_flag=True,
    default=False,
    help="Use each file's own certificate: integrity only, not identity.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def verify_signature_cmd(
    files: tuple[Path, ...],
    cert: Path | None,
    trust_embedded_cert: bool,
    output_format: str,
) -> None:
    """Verify the XML-DSig signature on each FILE (exit 0 = all valid).

    Needs the signer's certificate (--cert), or --trust-embedded-cert,
    which proves a file is unchanged since signing but not who signed
    it. Exit 1 when a file does not verify, 2 when the command cannot
    run.
    \f
    Args:
        files: Signed XML files.
        cert: The trust anchor, a PEM certificate or public key.
        trust_embedded_cert: Verify with each file's own certificate.
        output_format: ``text`` or ``json``.

    Raises:
        VerifyRefused: Without a trust choice, or without pain001[sign].
        SystemExit: 1 when a file does not verify.
    """
    if (cert is None) == (not trust_embedded_cert):
        raise VerifyRefused(
            "pass exactly one of --cert (the signer's certificate) or "
            "--trust-embedded-cert (integrity only)"
        )
    from pain001.security.dsig import (  # noqa: PLC0415
        XmlSignatureError,
        verify_signature,
    )

    try:
        anchor = None if cert is None else cert.read_bytes()
        reports = [
            (
                str(path),
                verify_signature(
                    path.read_bytes(),
                    trust_anchor=anchor,
                    trust_embedded_cert=trust_embedded_cert,
                ),
            )
            for path in files
        ]
    except (XmlSignatureError, ValueError) as exc:
        raise VerifyRefused(str(exc)) from exc
    if output_format == "json":
        click.echo(
            json.dumps(
                [{"file": name, **asdict(r)} for name, r in reports], indent=2
            )
        )
    else:
        click.echo("\n".join(_line(name, r) for name, r in reports))
    if not all(r.valid for _, r in reports):
        raise SystemExit(1)
