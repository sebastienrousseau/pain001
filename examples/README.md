<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Pain001 Examples

Runnable, self-checking examples of the workflows listed below. Each
script exits `0` on success and is executed in CI by
`tests/test_examples.py`, so they cannot silently drift out of date.

Run them from the repository root:

```bash
python examples/01_generate_xml_file.py
```

| Example | Feature shown |
|---|---|
| `01_generate_xml_file.py` | Library API: load CSV, render the bundled template, XSD-validate, write the XML file |
| `02_generate_xml_string.py` | In-memory `generate_xml_string` for APIs, serverless, and queues |
| `03_cli_workflows.py` | CLI dry-run, generation, and the documented exit codes (0 and 2) |
| `04_config_profiles.py` | Built-in configuration profiles via `ConfigManager` |
| `05_api_job_lifecycle.py` | REST API (`/api/v1`): health, sync validation, async job submit/poll/download, `DELETE /api/v1/jobs/{id}` (requires `pip install pain001[api]`) |
| `06_scheme_validation.py` | Scheme rulebook validation — all six scheme profiles (`sepa-sct`, `sepa-sdd`, `sepa-inst`, `sepa-b2b`, `xborder-ct`, `anti-duplicate`) including composition, structured violations + remediation, the rail profiles (`uk-chaps`, `ch-domestic` …) on rows projected from corpus files, and the ISO 20022 charset guard |
| `07_parse_bank_responses.py` | Parsing the messages banks send back (`pain.002` status reports, `camt.053` statements) and **building** a pain.002 that round-trips back through the parser |
| `08_version_migration.py` | Mapping payment data between pain.001 versions with `VersionMapper` |
| `09_streaming_large_batch.py` | Streaming generation: one validated XML file per input chunk |
| `10_input_formats.py` | Loading the same data from CSV, SQLite, JSON, JSON Lines and Parquet, including streaming Parquet parity (`parquet` extra) |
| `11_observability_metrics.py` | Metric callbacks (`register_metrics_callback`) for Prometheus/OpenTelemetry/log forwarding |
| `12_mcp_tools.py` | The MCP server's tools called directly (run the server with `pain001-mcp`; requires `pip install pain001[mcp]`) |
| `13_lsp_diagnostics.py` | The LSP diagnostic engine linting a CSV for bad IBAN/BIC/currency/charset and missing columns (editor server: `pain001-lsp`, `pip install pain001[lsp]`) |
| `14_redis_distributed.py` | v0.0.53 Redis-backed durable job store (`RedisJobStore`) + cross-replica rate limiter (`RedisFixedWindowBackend`); fakeredis-driven so the script runs without a Redis daemon (requires `pip install pain001[redis]`) |
| `15_example_corpus.py` | The example corpus: read API and coverage manifest, schema inventory and coverage of your own file, synthetic identifiers, building a scenario with an illustrative private overlay, the four-rung ladder and rail projection, ISO external code sets, the guideline derive tool on a synthetic guideline outside the repository, and `pain.008.001.08` generation |
| `16_iso_json_twins.py` | The ISO JSON twin of a corpus file (RA 2025 convention), validation against the per-edition JSON Schema, editing in JSON and encoding back through the XSD, the schema rejecting a bad decimal, and the records twin with its measured gap and regeneration through the CSV pipeline |
| `17_custom_policies.py` | Request-local CEL policies, exact decimal boundaries, warning severity and fail-closed errors (`rules` extra) |
| `18_review_only_corrections.py` | Deterministic text suggestions, unchanged inputs and protected financial fields |
| `19_plugin_dispatch.py` | A registered synthetic loader actually selected by eager and streaming input dispatch |
| `20_async_generation.py` | Every async wrapper (loading, string generation, `process_files_async` with `output_path`, `process_files_streaming_async` with `output_dir`, `validate_all_async`) checked against its synchronous result |
| `21_faces.py` | Faces: project a pain.001 payment into UK Open Banking v4.0.1, Berlin Group NextGenPSD2 v1.3.16 and ISO 2018 JSON with `project_face`, read each loss report, see a face refuse a document that lacks `InstrId`, and run `pain001 face` with bindings and `--loss-report` |
| `22_envelope_and_signing.py` | Wrap a generated pain.001 in a Business Application Header, unpack it, sign it with XML-DSig RSA-SHA256, verify it, and see a changed amount rejected (`pip install pain001[sign]`) |
| `23_streaming_output.py` | Stream XML as chunks and straight to a file with `stream_xml_chunks` / `stream_xml_to_file` (same bytes as `generate_xml_string`, XSD-valid), and what `normalize_payment_records` / `canonicalize_payment_record` do to a row |
| `24_templates_and_errors.py` | Query and guard the template registry (`DEFAULT_TEMPLATE_REGISTRY`, `TemplateRegistry`, `validate_registry`), catch `DataSourceError` and `PaymentValidationError`, inspect `SchemeValidationResult` / `SchemeViolation`, and receive `MetricEvent`s |
| `25_cli_plugins_and_upload.py` | `plugins list/show/disable`, `upload` (its offline refusals, then an SFTP round trip against a throwaway loopback server with password login and with a passphrase-protected private key, `upload` extra) and `serve --help`, with a temporary HOME |
| `26_rest_server.py` | `pain001 serve` started for real on a free loopback port: health check, `PAIN001_API_KEY` bearer auth (401 without, 200 with), validation over HTTP, and a graceful SIGTERM shutdown (`api` extra) |

Install the development environment with `poetry install --all-extras --with dev`
before running the complete suite. Examples illustrate workflows; they do not
prove every input, failure mode or feature combination. Focused regression
tests cover additional negative paths. See [verification coverage](../docs/verification-coverage.md)
for the evidence map and its limits.

Sample inputs live in `data/`: `payments.csv` (a copy of the bundled
`pain001/templates/pain.001.001.03/template.csv`, used by the CLI and
library examples) and `payments.json` (typed values for the REST API,
whose validation expects native JSON integers and booleans).
