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

"""What ``generate`` (and ``validate``, its dry run) does once parsed.

``cli.py`` declares the options; this module resolves them against
the configuration, runs the steps in :mod:`pain001.cli._generate_steps`
and, with ``--format json``, writes one result object to stdout.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from typing import Any

import click

from pain001.cli._config import _resolve_config
from pain001.cli._format import Failure, Reporter, deprecated, emit_json
from pain001.cli._generate_steps import (
    Outcome,
    check_schematron,
    emit_metric,
    failure_message,
    generate_files,
    validate_data,
)
from pain001.cli._gpg import _apply_gpg_options
from pain001.cli._info import show_template_list, show_template_metadata
from pain001.cli._logging import configure_logging, resolve_log_format
from pain001.cli._output import esc
from pain001.cli._paths import (
    _require_inputs,
    _require_message_type,
    _resolve_template_assets,
)
from pain001.logging_schema import Events, Fields, log_event
from pain001.observability import (
    clear_metrics_callbacks,
    register_metrics_callback,
)
from pain001.security.path_validator import trusted_paths

#: Options the configuration file or a profile can supply.
_PATH_KEYS = (
    "xml_template_file_path",
    "xsd_schema_file_path",
    "data_file_path",
)
_CONFIG_KEYS = (
    "xml_message_type",
    *_PATH_KEYS,
    "config_file",
    "output_dir",
    "streaming",
    "chunk_size",
    "profile",
    "emit_metrics",
)


def _resolve(rep: Reporter, opts: dict[str, Any]) -> dict[str, Any]:
    """Merge the configuration into ``opts`` and resolve the templates.

    Args:
        rep: Where human output goes.
        opts: The command's options; updated in place.

    Returns:
        The resolved configuration, for ``--show-config``.

    Raises:
        Failure: 2 when the message type or data file is missing or
            the message type is unknown.
    """
    given = {key: opts[key] for key in _CONFIG_KEYS}
    for key in _PATH_KEYS:
        given[key] = os.path.expanduser(given[key]) if given[key] else None
    resolved = _resolve_config(given)
    opts.update({key: resolved.get(key) for key in _CONFIG_KEYS})
    for key, label in (
        ("xml_message_type", "XML message type"),
        ("data_file_path", "data file path"),
    ):
        if not opts[key]:
            rep.error(f"[bold red]✗ Error:[/bold red] Missing {label}")
            raise Failure(2, f"Missing {label}")
    _require_message_type(rep.console, opts["xml_message_type"])
    opts["xml_template_file_path"], opts["xsd_schema_file_path"] = (
        _resolve_template_assets(
            opts["xml_message_type"],
            opts["xml_template_file_path"],
            opts["xsd_schema_file_path"],
        )
    )
    return resolved


def _show_config(
    rep: Reporter, resolved: dict[str, Any], opts: dict[str, Any]
) -> None:
    """Print the resolved configuration and template paths.

    Args:
        rep: Selects text or JSON.
        resolved: The merged configuration.
        opts: The resolved options.
    """
    paths = {
        "template": opts["xml_template_file_path"],
        "schema": opts["xsd_schema_file_path"],
    }
    if rep.as_json:
        emit_json({"config": resolved, **paths})
        return
    click.echo(repr(resolved))
    click.echo(repr(paths))


def _prepare(rep: Reporter, opts: dict[str, Any]) -> None:
    """Check the inputs exist and apply the side-effect options.

    Args:
        rep: Where human output goes.
        opts: The resolved options.
    """
    inputs = (
        opts["data_file_path"],
        opts["xml_template_file_path"],
        opts["xsd_schema_file_path"],
    )
    _require_inputs(rep.console, inputs)
    # The user named these files; they are read wherever they live.
    click.get_current_context().with_resource(trusted_paths(*inputs))
    if opts["emit_metrics"]:
        register_metrics_callback(emit_metric)
    _apply_gpg_options(opts["decrypt_key"], opts["decrypt_passphrase_env"])
    if opts["output_dir"]:
        os.makedirs(opts["output_dir"], exist_ok=True)
        rep.progress(
            f"[cyan]ℹ Output directory: {esc(opts['output_dir'])}[/cyan]"
        )


def _dry_run(
    rep: Reporter,
    outcome: Outcome,
    opts: dict[str, Any],
    logger: logging.Logger,
) -> None:
    """Validate everything and write nothing.

    Args:
        rep: Where human output goes.
        outcome: Records what was checked.
        opts: The resolved options.
        logger: The package logger.
    """
    validate_data(rep, outcome, opts, logger)
    if opts["schematron"]:
        check_schematron(rep, outcome, opts)
    log_event(
        logger,
        logging.INFO,
        Events.CLI_DRY_RUN,
        **{
            Fields.MESSAGE_TYPE: opts["xml_message_type"],
            "validation_passed": True,
            "record_count": outcome.records,
        },
    )
    rep.progress(
        "\n[bold green]✓ All validations passed[/bold green] "
        "[dim](--dry-run: no XML generated)[/dim]"
    )


def _pipeline(
    rep: Reporter,
    outcome: Outcome,
    opts: dict[str, Any],
    logger: logging.Logger,
) -> bool:
    """Resolve, check and run; return False when nothing was run.

    Args:
        rep: Where human output goes.
        outcome: Records what the run did.
        opts: The command's options.
        logger: The package logger.

    Returns:
        False for ``--show-config``, which prints instead of running.
    """
    resolved = _resolve(rep, opts)
    if opts["show_config"]:
        _show_config(rep, resolved, opts)
        return False
    outcome.message_type = opts["xml_message_type"]
    outcome.data_file = opts["data_file_path"]
    _prepare(rep, opts)
    log_event(
        logger,
        logging.INFO,
        Events.CLI_ARGS_PARSED,
        **{
            Fields.MESSAGE_TYPE: opts["xml_message_type"],
            "dry_run": opts["dry_run"],
        },
    )
    if opts["dry_run"]:
        _dry_run(rep, outcome, opts, logger)
    else:
        if opts["scheme"] or opts["rules"] is not None:
            validate_data(rep, outcome, opts, logger)
        generate_files(rep, outcome, opts)
    return True


def _listing(rep: Reporter, opts: dict[str, Any]) -> bool:
    """Handle ``--list-templates`` and ``--show-template``.

    Args:
        rep: Selects text or JSON.
        opts: The command's options.

    Returns:
        True when one of them was given and printed.
    """
    if opts["list_templates"]:
        show_template_list(rep.output_format)
        return True
    if opts["show_template"]:
        show_template_metadata(opts["show_template"], rep.output_format)
        return True
    return False


def run_generate(opts: dict[str, Any]) -> None:
    """Run ``generate`` with the options Click parsed.

    Args:
        opts: Every ``generate`` option, by parameter name.

    Raises:
        Failure: When the run fails; with ``--format json`` the result
            object, ``"ok": false``, is written first.
        click.ClickException: For a configuration error, likewise.
    """
    # JSON log records on stderr would be corrupted by progress lines.
    quiet = opts["quiet"] or resolve_log_format(opts["log_format"]) == "json"
    rep = Reporter(opts["output_format"], quiet)
    if opts["scheme_format"] == "json":
        deprecated("--scheme-format json", "--format json")
    rep.banner()
    logger = configure_logging(
        rep.chatter, opts["verbose"], opts["log_format"]
    )
    if _listing(rep, opts):
        return
    outcome = Outcome(dry_run=opts["dry_run"])
    try:
        ran = _pipeline(rep, outcome, opts, logger)
    except (Failure, click.ClickException) as exc:
        outcome.ok, outcome.error = False, failure_message(exc)
        if rep.as_json:
            emit_json(asdict(outcome), indent=None)
        raise
    finally:
        clear_metrics_callbacks()
    if ran and rep.as_json:
        emit_json(asdict(outcome), indent=None)
