# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Pin that ``init_otel`` builds the tracer once, for the named service.

The broader suite exercised ``init_otel`` through the real SDK, where
a second initialisation or a lost service name changed nothing it
asserted. Here ``_tracer_for`` is a spy, so no provider is ever
installed process-wide and the mutation run's survivors in
``init_otel`` (the once-only flag, the service name passed on) are
killed directly.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pain001.observability import otel


@pytest.fixture
def tracer_calls(monkeypatch) -> Iterator[list[str]]:
    """Enable tracing with a spy in place of the SDK tracer factory."""
    calls: list[str] = []

    def spy(service_name: str) -> str:
        calls.append(service_name)
        return f"tracer:{service_name}"

    monkeypatch.setenv(otel.OTEL_ENABLED_ENV, "true")
    monkeypatch.setattr(otel, "_tracer_for", spy)
    otel.reset_for_tests()
    yield calls
    otel.reset_for_tests()


def test_init_otel_passes_the_service_name(tracer_calls):
    """The caller's service name reaches the tracer factory."""
    assert otel.init_otel("acme-payments") == "tracer:acme-payments"
    assert tracer_calls == ["acme-payments"]


def test_init_otel_defaults_to_pain001(tracer_calls):
    """Without a name the service is ``pain001``."""
    assert otel.init_otel() == "tracer:pain001"
    assert tracer_calls == ["pain001"]


def test_init_otel_initialises_once(tracer_calls):
    """A second call returns the cached tracer without rebuilding it."""
    first = otel.init_otel("acme-payments")
    second = otel.init_otel("other-service")
    assert first == second == "tracer:acme-payments"
    assert tracer_calls == ["acme-payments"]


def test_init_otel_disabled_builds_nothing(tracer_calls, monkeypatch):
    """With tracing off no tracer is built, and none is cached."""
    monkeypatch.setenv(otel.OTEL_ENABLED_ENV, "false")
    assert otel.init_otel() is None
    assert otel.init_otel() is None
    assert tracer_calls == []
