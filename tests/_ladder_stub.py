# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Stub the validation ladder's loading rungs for CLI plumbing tests."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch


@contextmanager
def rows_loaded(rows: list[dict[str, Any]]) -> Iterator[MagicMock]:
    """Make the ladder load ``rows`` and pass them through the JSON Schema.

    The tests that use this drive the CLI's scheme and option handling
    with partial rows; the schema rung has its own tests.

    Args:
        rows: The rows the loader returns.

    Yields:
        The mock standing in for ``load_batch``.
    """
    with (
        patch(
            "pain001.validation.ladder.load_batch", return_value=rows
        ) as load,
        patch(
            "pain001.validation.ladder.SchemaValidator.validate_batch",
            return_value=(len(rows), len(rows), []),
        ),
    ):
        yield load
