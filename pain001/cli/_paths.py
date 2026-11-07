# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Path handling shared by the CLI commands."""

import os

import click

from pain001.templates import DEFAULT_TEMPLATE_REGISTRY


def _resolve_template_assets(
    xml_message_type: str,
    xml_template_file_path: str | None,
    xsd_schema_file_path: str | None,
) -> tuple[str, str]:
    """Resolve template/schema from registry when paths are omitted."""
    if xml_template_file_path and xsd_schema_file_path:
        return xml_template_file_path, xsd_schema_file_path
    template_path, schema_path = DEFAULT_TEMPLATE_REGISTRY.resolve_paths(
        xml_message_type
    )
    return (
        xml_template_file_path or template_path,
        xsd_schema_file_path or schema_path,
    )


def _file_not_directory(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    """Refuse a path ending in a separator: it names a directory.

    Click's ``dir_okay=False`` only catches directories that exist, so
    ``-o work/`` used to write a file named ``work``.

    Args:
        ctx: The Click context (unused).
        param: The option being checked (unused).
        value: The path given, if any.

    Returns:
        The path unchanged.

    Raises:
        click.BadParameter: If the path ends with a path separator.
    """
    if value is not None and value.endswith(("/", os.sep)):
        raise click.BadParameter(
            f"{value!r} is a directory path; give a file name, "
            "for example -o payments.csv."
        )
    return value
