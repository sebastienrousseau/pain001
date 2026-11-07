# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Configuration resolution for the CLI, with errors as usage errors."""

from collections.abc import Mapping
from typing import Any

import click
import yaml

from pain001.config import ConfigManager


def _resolve_config(
    cli_args: Mapping[str, Any], manager: ConfigManager | None = None
) -> dict[str, Any]:
    """Resolve the layered configuration, reporting bad input cleanly.

    Args:
        cli_args: Values given on the command line (None when absent).
        manager: The configuration manager; a default one when omitted.

    Returns:
        The merged configuration.

    Raises:
        click.UsageError: If a config file is not valid YAML, the
            profile is unknown or the merged configuration is invalid;
            these used to end in a traceback.
    """
    try:
        return (manager or ConfigManager()).resolve(dict(cli_args))
    except yaml.YAMLError as exc:
        name = cli_args.get("config_file") or "the configuration file"
        raise click.UsageError(f"{name} is not valid YAML: {exc}") from exc
    except (KeyError, ValueError) as exc:
        message = exc.args[0] if exc.args else str(exc)
        raise click.UsageError(str(message)) from exc
