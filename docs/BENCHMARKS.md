<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Benchmark methodology

No hardware-independent throughput claim is made. Run `poetry run make perf`
to produce `.benchmarks/results.json` with pytest-benchmark measurements and
environment metadata. The quality workflow uploads benchmark artefacts.
`benches/` also exercises generation and corpus operations.

Compare runs only with recorded Python, dependency and hardware versions,
equivalent synthetic inputs, and the same warm-up/iteration configuration.
Passing a benchmark smoke test means it executes, not that a latency service
level or a bank's processing deadline is guaranteed. The mockbank one-second
round-trip acceptance test is a synthetic local integration check, not a
production throughput benchmark.

## Ten-plugin cold discovery

Run `poetry run python benches/bench_plugin_discovery.py`. It creates ten
synthetic distributions with real entry-point metadata in a temporary site
directory, then measures imports and discovery in three fresh interpreters.
It asserts discovery of all ten, not a latency threshold. The fixtures are
not installed into the user's environment and are removed after the run.

On 2026-09-25, Python 3.12.14 on macOS 26.7 arm64 measured 0.674, 0.525 and
0.532 seconds in the development environment. These are environment-specific
observations, not a startup SLA or independent external-author validation.
