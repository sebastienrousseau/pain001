# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Registry population under concurrency and re-entry.

Population is lazy, so the first lookups in a process race each other.
These tests force the interleaving instead of hoping for it: the
built-in registration step is replaced by one that parks on an event,
so a second thread is guaranteed to look up while the first is still
populating.
"""

from __future__ import annotations

import threading
from importlib import import_module
from unittest.mock import patch

import pytest

from pain001.plugins import PAIN001_API_VERSION, PluginMeta
from pain001.plugins.registry import PluginRegistry

registry_mod = import_module("pain001.plugins.registry")
builtins_mod = import_module("pain001.plugins._builtins")

WAIT = 5.0


class _Writer:
    """Minimal writer plugin; only ``meta`` matters to the registry."""

    meta = PluginMeta(
        name="slow-writer",
        version="1.0.0",
        description="Writer registered while another thread waits.",
        api_version=PAIN001_API_VERSION,
    )


def test_lookup_during_population_waits_for_it():
    """A second thread never sees the half-populated registry."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    started = threading.Event()
    release = threading.Event()
    seen: list[object] = []

    def slow_register_all(target: PluginRegistry) -> None:
        started.set()
        assert release.wait(WAIT)
        target.register_writer(_Writer())

    def first() -> None:
        reg.get_writer("slow-writer")

    def second() -> None:
        seen.append(reg.get_writer("slow-writer"))

    with (
        patch.object(builtins_mod, "register_all", slow_register_all),
        patch.object(registry_mod, "_iter_entry_points", return_value=[]),
    ):
        populator = threading.Thread(target=first)
        populator.start()
        assert started.wait(WAIT)
        reader = threading.Thread(target=second)
        reader.start()
        # The old code returned None here at once; the fix blocks.
        reader.join(0.2)
        release.set()
        populator.join(WAIT)
        reader.join(WAIT)
    assert seen and seen[0] is not None
    assert seen[0].meta.name == "slow-writer"


def test_concurrent_first_lookups_all_see_builtins():
    """Eight threads released together all find the built-in writer.

    The writer registers last among the built-ins, so it is the lookup
    most exposed to a registry that flags itself populated too early.
    """
    threads = 8
    reg = PluginRegistry(PAIN001_API_VERSION)
    barrier = threading.Barrier(threads)
    results: list[object] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait(WAIT)
        found = reg.get_writer("xml-file")
        with lock:
            results.append(found)

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join(WAIT)
    assert len(results) == threads
    assert all(found is not None for found in results)


def test_reentrant_lookup_during_population_does_not_deadlock():
    """A plugin that looks the registry up while registering returns."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    inner: list[object] = []

    def reentrant_register_all(target: PluginRegistry) -> None:
        inner.append(target.get_writer("slow-writer"))
        target.register_writer(_Writer())

    with (
        patch.object(builtins_mod, "register_all", reentrant_register_all),
        patch.object(registry_mod, "_iter_entry_points", return_value=[]),
    ):
        outer = reg.get_writer("slow-writer")
    assert inner == [None]
    assert outer is not None


def test_failed_population_is_retried():
    """A population that raises leaves the registry unpopulated."""
    reg = PluginRegistry(PAIN001_API_VERSION)
    calls: list[int] = []

    def flaky_register_all(target: PluginRegistry) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first population fails")
        target.register_writer(_Writer())

    with (
        patch.object(builtins_mod, "register_all", flaky_register_all),
        patch.object(registry_mod, "_iter_entry_points", return_value=[]),
    ):
        with pytest.raises(RuntimeError):
            reg.get_writer("slow-writer")
        assert reg.get_writer("slow-writer") is not None
    assert len(calls) == 2
