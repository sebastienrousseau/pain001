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

"""The steps ``generate`` and ``validate`` run, and what they found.

Each step prints for a person on stderr through a
:class:`~pain001.cli._format.Reporter` and records its result on an
:class:`Outcome`, which ``--format json`` writes to stdout.
"""

from __future__ import annotations

import logging
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

from pain001.cli._format import Failure, Reporter, emit_json
from pain001.cli._hints import print_data_tip, read_text
from pain001.cli._output import esc, print_scheme_result
from pain001.core.core import process_files, process_files_streaming
from pain001.logging_schema import log_validation_event
from pain001.observability import MetricEvent
from pain001.validation import SchemeValidationResult, validate_scheme
from pain001.validation._one_batch import load_batch
from pain001.xml.envelope import BusinessApplicationHeader


@dataclass
class Outcome:
    """What one ``generate`` or ``validate`` run did, for ``--format json``.

    Attributes:
        ok: False when the run exits non-zero.
        message_type: The resolved ISO 20022 message type.
        data_file: The payment data that was read.
        records: Rows validated, when the data was validated.
        dry_run: True for ``validate`` and ``generate --dry-run``.
        output_dir: Where XML was written.
        files: The XML files written, in order.
        scheme: The scheme or policy result, when one was asked for.
        schematron: The Schematron result of a dry run, when asked for.
        error: Why the run failed, as plain text.
    """

    ok: bool = True
    message_type: str | None = None
    data_file: str | None = None
    records: int | None = None
    dry_run: bool = False
    output_dir: str | None = None
    files: list[str] = field(default_factory=list)
    scheme: dict[str, Any] | None = None
    schematron: dict[str, Any] | None = None
    error: str | None = None


def emit_metric(event: MetricEvent) -> None:
    """Write one metric event to stdout as a JSON line (NDJSON).

    Args:
        event: The metric the pipeline emitted.
    """
    emit_json(
        {
            "metric": event.name,
            "timestamp": event.timestamp,
            "attributes": event.attributes,
            "trace_context": event.trace_context,
        },
        indent=None,
    )


def _scheme_result(
    data: list[dict[str, Any]],
    scheme: str,
    rules: str | None,
    message_type: str,
) -> SchemeValidationResult:
    """Check rows against a scheme, or a private policy when given.

    Args:
        data: Loaded payment rows.
        scheme: Scheme profile name.
        rules: Optional path to a private YAML policy file.
        message_type: Schema used for policy numeric types.

    Returns:
        The scheme or policy result.

    Raises:
        ValueError: For an unknown scheme or a missing ``pain001[rules]``.
    """
    if rules is None:
        return validate_scheme(data, scheme, message_type=message_type)
    try:
        from pain001.validation.policy import (  # noqa: PLC0415
            MAX_POLICY_BYTES,
            validate_policy,
        )
    except ImportError as exc:
        raise ValueError("Custom rules require 'pain001[rules]'.") from exc
    with Path(rules).open(encoding="utf-8") as policy_file:
        source = policy_file.read(MAX_POLICY_BYTES + 1)
    return validate_policy(data, source, scheme, message_type)


def scheme_dict(result: SchemeValidationResult) -> dict[str, Any]:
    """The JSON form of a scheme result.

    Args:
        result: A scheme or policy result.

    Returns:
        ``profile``, ``is_valid`` and ``violations``.
    """
    return {
        "profile": result.profile,
        "is_valid": result.is_valid,
        "violations": [v.as_dict() for v in result.violations],
    }


def run_scheme_check(
    rep: Reporter,
    outcome: Outcome,
    data: list[dict[str, Any]],
    opts: dict[str, Any],
) -> None:
    """Validate loaded rows against a payment-scheme rulebook.

    ``--scheme-format json`` (deprecated) still writes the scheme
    result alone to stdout when ``--format`` is text.

    Args:
        rep: Where human output goes.
        outcome: Records the scheme result.
        data: Loaded payment rows.
        opts: The command's options (``scheme``, ``rules``,
            ``explain``, ``scheme_format``, ``xml_message_type``).

    Raises:
        Failure: 2 for an unknown scheme or missing extra, 1 when rows
            violate it.
    """
    scheme = opts["scheme"] or "custom"
    legacy = opts["scheme_format"] == "json" and not rep.as_json
    try:
        result = _scheme_result(
            data, scheme, opts["rules"], opts["xml_message_type"]
        )
    except ValueError as exc:
        if legacy:
            emit_json({"error": str(exc)}, indent=None)
        rep.error(str(exc), plain=True)
        raise Failure(2, str(exc)) from exc
    outcome.scheme = scheme_dict(result)
    if legacy:
        emit_json(outcome.scheme, indent=None)
    elif not rep.as_json:
        print_scheme_result(rep.console, result, scheme, opts["explain"])
    if not result.is_valid:
        raise Failure(1, f"Scheme '{scheme}' validation failed")


def validate_data(
    rep: Reporter,
    outcome: Outcome,
    opts: dict[str, Any],
    logger: logging.Logger,
) -> None:
    """Load and validate the payment data, then any scheme or policy.

    Args:
        rep: Where human output goes.
        outcome: Records the row count and scheme result.
        opts: The command's resolved options.
        logger: Logger for the validation events.

    Raises:
        Failure: 1 when the data does not load or validate.
    """
    path, message_type = opts["data_file_path"], opts["xml_message_type"]
    rep.progress("[cyan]→ Validating payment data...[/cyan]")
    try:
        data = load_batch(path, message_type, opts["identifier_checks"])
        log_validation_event(
            logger, "payment_data", True, message_type=message_type
        )
        outcome.records = len(data)
        rep.progress(
            f"[bold green]✓ Data validation passed[/bold green] "
            f"({len(data)} payment records)"
        )
        if opts["scheme"] or opts["rules"] is not None:
            run_scheme_check(rep, outcome, data, opts)
    except Exception as e:
        log_validation_event(
            logger, "payment_data", False, e, message_type=message_type
        )
        rep.error(f"[bold red]✗ Data validation failed:[/bold red] {esc(e)}")
        print_data_tip(rep.console, path)
        raise Failure(1, f"Data validation failed: {e}") from e


def check_schematron(
    rep: Reporter, outcome: Outcome, opts: dict[str, Any]
) -> None:
    """Render the XML in memory and run the Schematron rulebook on it.

    Args:
        rep: Where human output goes.
        outcome: Records the Schematron result.
        opts: The command's resolved options.

    Raises:
        Failure: 1 when the rulebook fails.
    """
    from pain001.data.loader import load_payment_data  # noqa: PLC0415
    from pain001.schematron import validate_schematron  # noqa: PLC0415
    from pain001.xml.generate_xml import generate_xml_string  # noqa: PLC0415

    rulebook = opts["schematron"]
    xml_str = generate_xml_string(
        load_payment_data(opts["data_file_path"], opts["identifier_checks"]),
        opts["xml_message_type"],
        opts["xml_template_file_path"],
        opts["xsd_schema_file_path"],
    )
    result = validate_schematron(xml_str, rulebook=rulebook)
    outcome.schematron = result.to_dict()
    if not result.is_valid:
        rep.error(
            f"\n[bold red]✗ Schematron rulebook '{esc(rulebook)}' failed:"
            f"[/bold red]\n{esc(result.format_report())}",
        )
        raise Failure(1, f"Schematron rulebook '{rulebook}' failed")
    rep.progress(
        f"[bold green]✓ Schematron rulebook '{esc(rulebook)}' passed"
        f"[/bold green] ({result.rules_passed}/{result.rules_evaluated} rules)"
    )


def _shared_kwargs(opts: dict[str, Any]) -> dict[str, Any]:
    """Envelope, signing, Schematron and identifier keyword arguments.

    Args:
        opts: The command's resolved options.

    Returns:
        The keyword arguments both generation paths take.
    """
    bah_header = None
    bah = (opts["bah_sender"], opts["bah_receiver"], opts["bah_msg_id"])
    if opts["envelop_bah"] or any(bah):
        bah_header = BusinessApplicationHeader(
            from_bic=bah[0], to_bic=bah[1], biz_msg_idr=bah[2]
        )
    passphrase_env = opts["xml_sign_passphrase_env"]
    return {
        "envelop_bah": opts["envelop_bah"],
        "bah_header": bah_header,
        "xml_sign_key": read_text(opts["xml_sign_key"]),
        "xml_sign_cert": read_text(opts["xml_sign_cert"]),
        "xml_sign_passphrase": (
            os.environ.get(passphrase_env) if passphrase_env else None
        ),
        "schematron": opts["schematron"],
        "identifier_checks": opts["identifier_checks"],
    }


def _write(opts: dict[str, Any], output_dir: str) -> list[str]:
    """Generate the XML files and return their paths.

    Args:
        opts: The command's resolved options.
        output_dir: Absolute output directory.

    Returns:
        The files written, in order.
    """
    message_type = opts["xml_message_type"]
    args = (
        message_type,
        opts["xml_template_file_path"],
        opts["xsd_schema_file_path"],
        opts["data_file_path"],
    )
    if opts["streaming"]:
        written = process_files_streaming(
            *args,
            chunk_size=opts["chunk_size"],
            output_dir=output_dir,
            **_shared_kwargs(opts),
        )
        return [str(path) for path in written]
    output_path = os.path.join(output_dir, f"{message_type}.xml")
    process_files(*args, output_path=output_path, **_shared_kwargs(opts))
    return [output_path]


def generate_files(
    rep: Reporter, outcome: Outcome, opts: dict[str, Any]
) -> None:
    """Generate XML payment files.

    The output location is resolved explicitly instead of chdir-ing
    into it: changing the working directory re-anchored relative data
    and template paths.

    Args:
        rep: Where human output goes.
        outcome: Records the output directory and files.
        opts: The command's resolved options.

    Raises:
        Failure: 1 when generation fails.
    """
    rep.progress("[cyan]→ Generating XML payment files...[/cyan]")
    output_dir = opts["output_dir"]
    outcome.output_dir = (
        os.path.realpath(output_dir) if output_dir else os.getcwd()
    )
    try:
        outcome.files = _write(opts, outcome.output_dir)
    except Exception as e:
        rep.error(f"[bold red]✗ Generation failed:[/bold red] {esc(e)}")
        if opts["verbose"]:
            rep.console.print("\n[yellow]Traceback:[/yellow]")
            rep.console.print(traceback.format_exc(), markup=False)
        raise Failure(1, f"Generation failed: {e}") from e
    rep.progress(
        f"\n[bold green]✓ Success![/bold green] XML files generated "
        f"successfully.\n[cyan]Message Type:[/cyan] "
        f"{esc(opts['xml_message_type'])}\n"
        f"[cyan]Output Location:[/cyan] {esc(outcome.output_dir)}"
    )


def failure_message(exc: Failure | click.ClickException) -> str:
    """The plain-text reason a run stopped.

    Args:
        exc: The exit or Click error.

    Returns:
        Its message.
    """
    if isinstance(exc, Failure):
        return exc.message
    return exc.format_message()
