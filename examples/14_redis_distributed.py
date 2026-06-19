# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Redis-backed distributed job store + rate limiter (v0.0.53 NEW).

The REST API ships two pluggable backends behind public Protocols so
multi-replica deployments can share state without contention:

* ``pain001.api.job_store.RedisJobStore``    - async-job state, durable
  across restarts and shared between replicas.
* ``pain001.api.ratelimit.RedisFixedWindowBackend`` - per-client
  request cap enforced across replicas (in-process limiter only
  protects one worker; this one protects the deployment).

Both are exercised against ``fakeredis`` so the example runs in CI
without a Redis daemon. In production point them at a real
``redis://`` URL via:

    PAIN001_JOB_STORE_URL=redis://my-redis:6379/0
    PAIN001_RATE_LIMIT_BACKEND=redis
    PAIN001_RATE_LIMIT_REDIS_URL=redis://my-redis:6379/0  # (or reuse JOB_STORE_URL)

Run from the repository root::

    python examples/14_redis_distributed.py
"""

import fakeredis

from pain001.api.job_store import RedisJobStore
from pain001.api.ratelimit import RedisFixedWindowBackend


class _FakeClock:
    """Deterministic time source for the rate-limit window."""

    def __init__(self) -> None:
        """Start the clock at a stable epoch second."""
        self.now = 1_000_000.0

    def __call__(self) -> float:
        """Return the current time (callable interface required by limiter)."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds``."""
        self.now += seconds


def _job_store_round_trip() -> None:
    """RedisJobStore: durable save + load_all + delete round-trip."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = RedisJobStore(client=client, namespace="example:jobs")

    # Save two jobs, load them all back, then delete one.
    store.save("job-1", {"id": "job-1", "status": "pending"})
    store.save("job-2", {"id": "job-2", "status": "running"})
    loaded = store.load_all()
    assert set(loaded) == {"job-1", "job-2"}
    assert loaded["job-2"]["status"] == "running"
    store.delete("job-1")
    assert "job-1" not in store.load_all()
    print(
        f"RedisJobStore: saved 2 jobs, loaded {len(loaded)}, "
        "deleted 1; survives a restart because it's in Redis."
    )


def _rate_limiter_cross_replica() -> None:
    """RedisFixedWindowBackend: cap shared across two replicas."""
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    clock = _FakeClock()
    # Two replicas point at the same Redis with the same cap.
    replica_a = RedisFixedWindowBackend(
        max_requests=3, window_seconds=60.0, client=client, clock=clock
    )
    replica_b = RedisFixedWindowBackend(
        max_requests=3, window_seconds=60.0, client=client, clock=clock
    )

    # 2 hits via A + 1 via B = 3 total; combined 4th hit is rejected.
    assert replica_a.is_allowed("client-1")
    assert replica_b.is_allowed("client-1")
    assert replica_a.is_allowed("client-1")
    assert not replica_b.is_allowed("client-1")
    print(
        "RedisFixedWindowBackend: two replicas + one Redis = one shared "
        "cap (3/minute). The 4th request was rejected by replica B "
        "even though replica A served the first three."
    )

    # Once the window elapses, the bucket frees up again.
    clock.advance(60.0)
    assert replica_b.is_allowed("client-1")
    print("Window reset: bucket free again after the 60s window elapsed.")


def _env_driven_selection() -> None:
    """Operators flip backends via env vars; no code change needed."""
    # The backend factory in pain001.api.ratelimit reads:
    #   PAIN001_RATE_LIMIT_BACKEND      = "memory" | "redis"  (default memory)
    #   PAIN001_RATE_LIMIT_REDIS_URL    = "redis://..."
    #   PAIN001_RATE_LIMIT              = "100/minute"
    # The job store mirrors the pattern via PAIN001_JOB_STORE_URL.
    print(
        "Env-driven selection: set PAIN001_RATE_LIMIT_BACKEND=redis "
        "(and PAIN001_RATE_LIMIT_REDIS_URL) to flip the limiter to "
        "Redis without changing pain001 code."
    )


def main() -> None:
    """Run the three demonstrations back-to-back."""
    _job_store_round_trip()
    _rate_limiter_cross_replica()
    _env_driven_selection()
    print("Redis distributed-backends example completed.")


if __name__ == "__main__":
    main()
