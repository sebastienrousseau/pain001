# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""Pin that a failed population clears the ``_populating`` flag to False.

``test_plugins_registry_reliability.py`` shows a failed population is
retried, which any falsy value allows; the mutation run kept a mutant
that reset the flag to ``None``. The flag is documented as a bool, so
this test pins the exact value the ``finally`` block restores.
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest

from pain001.plugins import PAIN001_API_VERSION
from pain001.plugins.registry import PluginRegistry

registry_mod = import_module("pain001.plugins.registry")
builtins_mod = import_module("pain001.plugins._builtins")


def _fail(_registry: PluginRegistry) -> None:
    """A built-in registration step that always fails."""
    raise RuntimeError("population fails")


def test_failed_population_resets_flag_to_false() -> None:
    """After the failure the registry is idle and unpopulated."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    with (
        patch.object(builtins_mod, "register_all", _fail),
        patch.object(registry_mod, "_iter_entry_points", return_value=[]),
        pytest.raises(RuntimeError, match="population fails"),
    ):
        reg.get_writer("any")
    assert reg._populating is False
    assert reg._populated is False
