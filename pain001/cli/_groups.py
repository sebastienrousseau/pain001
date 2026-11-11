# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The ``pain001`` command group and its default subcommand."""

from __future__ import annotations

import click


class DefaultGroup(click.Group):
    """Click group that falls back to a default subcommand.

    Preserves backwards compatibility: an invocation that does not name a
    subcommand (the long-documented ``pain001 -t ... -d ...``) is routed
    to ``generate`` so existing scripts and one-liners keep working.
    """

    #: Subcommand invoked when the first token is not a subcommand.
    default_command = "generate"

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Inject the default command when no subcommand is named.

        Args:
            ctx: The active Click context.
            args: Raw command-line arguments passed to the group.

        Returns:
            The residual arguments after the group has parsed its own.
        """
        if (
            args
            and args[0] not in self.commands
            and args[0] not in ("-h", "--help", "-V", "--version")
        ):
            args = [self.default_command, *args]
        return super().parse_args(ctx, args)
