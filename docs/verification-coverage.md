<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Verification coverage and limits

The required gate is **100% measured line and branch coverage** of `pain001`,
which is stricter than 98%. `poetry run make test` enforces it using the complete
unit/integration suite, not a separately classified unit-only suite. Coverage
exclusions remain visible in `pyproject.toml`; no new exclusions are introduced
to achieve this result. A coverage percentage proves execution, not that every
possible input, combination or financial interpretation is correct.

## Feature evidence map

The following map identifies executable evidence, not a claim of exhaustive
behavioral coverage. Test files include positive and negative cases; examples
are representative workflows. Paths in this table are repository-relative.

| Feature family | Regression evidence | Executable example or integration |
| :--- | :--- | :--- |
| Message families and XML output | `tests/test_regression_suite.py`, `tests/test_golden_files.py`, `tests/test_bundled_examples.py` | `examples/01_generate_xml_file.py`, `examples/02_generate_xml_string.py`, `examples/15_example_corpus.py` |
| CLI and configuration | `tests/test_cli_subcommands.py`, `tests/test_cli_error_paths.py`, `tests/test_config_manager.py` | `examples/03_cli_workflows.py`, `examples/04_config_profiles.py` |
| REST jobs and request validation | `tests/test_job_manager.py`, `tests/test_policy_interfaces.py`, `tests/test_regression_suite.py` | `examples/05_api_job_lifecycle.py` |
| Scheme, rail and charset rules | `tests/test_schemes.py`, `tests/test_rails.py` | `examples/06_scheme_validation.py` |
| Bank responses and response generation | `tests/test_pain002_generator.py`, `tests/test_camt053_generator.py`, `tests/test_regression_suite.py` | `examples/07_parse_bank_responses.py` |
| Migration | `tests/test_safety_migration.py`, `tests/test_regression_suite.py` | `examples/08_version_migration.py` |
| Streaming and input formats | `tests/test_streaming_loaders.py`, `tests/test_parquet_loader.py`, `tests/test_regression_suite.py` | `examples/09_streaming_large_batch.py`, `examples/10_input_formats.py` |
| Metrics and tracing | `tests/test_observability_otel.py`, `tests/test_regression_suite.py` | `examples/11_observability_metrics.py` |
| MCP and LSP adapters | `tests/test_mcp_server.py`, `tests/test_plugins_companions.py` | `examples/12_mcp_tools.py`, `examples/13_lsp_diagnostics.py` |
| Redis persistence and rate limits | `tests/test_redis_job_store.py`, `tests/test_redis_rate_limiter.py` | `examples/14_redis_distributed.py` (synthetic Redis) |
| Corpus, overlays, schema inventories and JSON twins | `tests/test_corpus_builder.py`, `tests/test_corpus_coverage.py`, `tests/test_twins_schema.py`, `tests/test_twins_records.py` | `examples/15_example_corpus.py`, `examples/16_iso_json_twins.py` |
| CEL policies | `tests/test_custom_policy.py`, `tests/test_policy_interfaces.py` | `examples/17_custom_policies.py` |
| Review-only corrections | `tests/test_record_corrections.py` | `examples/18_review_only_corrections.py` |
| Plugin contracts and execution | `tests/test_plugins_contract.py`, `tests/test_plugin_dispatch.py`, `tests/test_plugins_builtin_schemes_writer.py` | `examples/19_plugin_dispatch.py` |
| Async wrappers | `tests/test_async_adapter.py`, `tests/test_async_adapters.py` | `examples/20_async_generation.py` |
| SFTP trust, atomic upload and retries | `tests/test_sftp_upload.py`, `tests/test_sftp_cli.py` | `tests/test_sftp_roundtrip.py` (real loopback SSH/SFTP, synthetic credentials) |
| Encryption and security boundaries | `tests/test_plugins_gpg.py`, `tests/test_plugins_gpg_keyfile.py`, `tests/test_template_security.py`, `tests/test_code_scanning_regressions.py` | Focused regression fixtures; no real keys, bank accounts or external bank connection |

Companion XLSX, MCP correction tools, the plugin template and mockbank require
their own native suites; core coverage does not measure another repository.
See [issue acceptance](issue-audit.md). Independent plugin-author validation,
live-bank certification and historical independent review remain outside what
local tests can establish.

## Examples and benchmarks

`tests/test_examples.py` discovers every numbered example and every
`benches/bench_*.py` script. Missing extras and nonzero exits fail verification.
Every example must also appear in the examples guide. New benchmark entry points
must either accept the default smoke invocation or declare their quick mode in
the runner.

`benches/bench_features.py` measures every numbered example in a fresh process
and records Python/platform metadata. The benchmark CI job preserves its JSON
alongside pytest-benchmark results. These are workflow smoke timings, not
microbenchmarks and not a claim that every feature has an independent speed SLA.
SFTP and encrypted inputs use dedicated correctness tests instead of misleading
network or cryptography timing budgets.

The generation benchmark asserts transaction-count preservation and chunk
counts. The corpus benchmark requires nonempty XML, a valid JSON twin with
round-trip parity, and a complete generated schema coverage set. Plugin discovery
requires all ten synthetic installed plugins. `make perf` separately retains
the existing XML-generation performance guard. See [methodology](BENCHMARKS.md).

Mutation testing evaluates assertion strength separately from line coverage.
The existing fast-tier floor is 80%, not 100%; a surviving mutant requires
investigation and cannot honestly be described as exhaustive functional proof.

## Reproduce

```bash
poetry install --all-extras --with dev,docs
poetry run make check
poetry run make type
poetry run make perf
poetry run python benches/bench_features.py
poetry run make mutate-fast
```

Do not run simultaneous coverage sessions against the same `.coverage` file.
The complete suite supplies the release coverage result; a targeted test run is
diagnostic evidence only. Never reduce the gate or ignore failures to obtain a
green report.
