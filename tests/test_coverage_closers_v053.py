# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Targeted coverage-closer tests for v0.0.53 (line + branch -> 100%).

Five branches were uncovered by the broader regression suite:

1. ``pain001.api.app._gate_output_dir``: the loop-back path when the
   first allowed root rejects the candidate but the second accepts.
2. ``pain001.api.job_store.RedisJobStore.load_all``: the
   ``raw is None`` skip (a key disappeared between SCAN + GET).
3. Same: the ``isinstance(raw, bytes)`` decode path (Redis client
   configured with ``decode_responses=False``).
4. Same: the multi-page SCAN path (cursor wraps back to 0 only
   after a second iteration).
5. ``pain001.observability._current_trace_context``: the
   ``except ImportError`` branch when ``opentelemetry`` is absent.

Each test is small, isolated, and explicitly tagged with the
covered branch so future regressions point at the right place.
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import fakeredis

from pain001 import observability
from pain001.api.app import _gate_output_dir
from pain001.api.job_store import RedisJobStore


# ---------------------------------------------------------------------------
# 1. _gate_output_dir loop-back (app.py:198 -> 193)
# ---------------------------------------------------------------------------
def test_gate_output_dir_falls_through_first_root_into_tempdir(monkeypatch):
    """An output_dir matching the *second* allowed root (tmp) is accepted.

    The function iterates ``(cwd, tmp)``; a path that fails the
    commonpath check against cwd but matches tmp must be accepted.
    Patching ``os.path.commonpath`` deterministically forces False
    on iter 1 and True on iter 2, so the back-edge from line 198 to
    line 193 in pain001.api.app._gate_output_dir is exercised.
    """
    app_module = importlib.import_module("pain001.api.app")
    real_realpath = app_module.os.path.realpath

    # Two-iteration deterministic stub: first returns ``/`` (no match),
    # second returns whatever the real base is (match).
    call_state = {"n": 0}

    def stub_commonpath(paths):
        call_state["n"] += 1
        if call_state["n"] == 1:
            return "/"
        # Real result for the second call - tmp == tmp.
        return paths[1]

    monkeypatch.setattr(app_module.os.path, "commonpath", stub_commonpath)
    # Use a real, existing path so _validate_safe_path is happy.
    candidate = str(Path(tempfile.gettempdir()).resolve())
    resolved = _gate_output_dir(candidate)
    assert resolved == Path(real_realpath(candidate))
    assert call_state["n"] == 2, "expected two iterations of the for-loop"


# ---------------------------------------------------------------------------
# 2. RedisJobStore.load_all - raw is None (job_store.py:194)
# ---------------------------------------------------------------------------
def test_load_all_skips_key_that_vanished_between_scan_and_get():
    """A key returned by SCAN but absent from GET is skipped silently.

    This races on a real Redis when the key is deleted between the
    two commands; we simulate it by patching ``GET`` to return
    ``None`` for one of the keys SCAN returned.
    """
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = RedisJobStore(client=client, namespace="pain001:jobs")
    store.save("kept", {"id": "kept", "status": "done"})
    store.save("vanished", {"id": "vanished", "status": "done"})

    real_get = client.get

    def get_with_one_miss(key):
        if key.endswith(":vanished"):
            return None
        return real_get(key)

    with patch.object(client, "get", side_effect=get_with_one_miss):
        loaded = store.load_all()
    assert "kept" in loaded
    assert "vanished" not in loaded


# ---------------------------------------------------------------------------
# 3. RedisJobStore.load_all - bytes decode (job_store.py:196)
# ---------------------------------------------------------------------------
def test_load_all_decodes_bytes_when_decode_responses_is_false():
    """A Redis client returning ``bytes`` is decoded to ``str`` in-loop.

    Production deployments may run Redis clients with
    ``decode_responses=False`` (the lower-overhead default). The
    loader must handle both string and bytes values transparently.
    """
    client = fakeredis.FakeStrictRedis(decode_responses=False)
    store = RedisJobStore(client=client, namespace="pain001:jobs")
    store.save("alpha", {"id": "alpha", "status": "done"})

    loaded = store.load_all()
    assert "alpha" in loaded
    assert loaded["alpha"]["status"] == "done"


# ---------------------------------------------------------------------------
# 4. RedisJobStore.load_all - multi-page SCAN (job_store.py:201 -> 184)
# ---------------------------------------------------------------------------
def test_load_all_paginates_when_scan_returns_non_zero_cursor():
    """The while-loop continues when SCAN returns a non-zero cursor.

    Forces two SCAN iterations by patching the client's ``scan``
    method to emit half the keys on the first call (with a non-zero
    cursor) and the rest on the second call (with cursor 0).
    """
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = RedisJobStore(client=client, namespace="pain001:jobs")
    for n in range(4):
        store.save(f"j{n}", {"id": f"j{n}", "status": "done"})

    real_scan = client.scan
    calls: list[int] = []

    def paginated_scan(cursor=0, match=None, count=None):
        calls.append(cursor)
        # Drive the loop ourselves to guarantee cursor != 0 on first hit.
        if not calls or len(calls) == 1:
            new_cursor, keys = real_scan(cursor=0, match=match, count=count)
            return 1, keys[:2]  # advertise more pages via non-zero cursor
        new_cursor, keys = real_scan(cursor=0, match=match, count=count)
        return 0, keys[2:]

    with patch.object(client, "scan", side_effect=paginated_scan):
        loaded = store.load_all()
    assert len(calls) == 2, "two SCAN pages should have been requested"
    assert set(loaded.keys()) == {"j0", "j1", "j2", "j3"}


# ---------------------------------------------------------------------------
# 5. observability._current_trace_context - opentelemetry missing
# (observability/__init__.py:73-74)
# ---------------------------------------------------------------------------
def test_current_trace_context_returns_empty_when_opentelemetry_absent(
    monkeypatch,
):
    """When ``opentelemetry`` is not installed the helper returns ``{}``.

    OTel is an optional dep; pain001's metric-event surface must not
    require it. We force ``import opentelemetry`` to fail and reload
    the module so the cached import is invalidated.
    """
    # Make `import opentelemetry` raise inside _current_trace_context.
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    importlib.reload(observability)
    assert observability._current_trace_context() == {}
    # Restore by re-loading once monkeypatch unwinds (autouse cleanup
    # in pytest handles sys.modules; importlib.reload below is a
    # belt-and-braces step so the rest of the suite gets the real
    # module back).
    monkeypatch.undo()
    importlib.reload(observability)
