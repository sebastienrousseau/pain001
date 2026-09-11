# Pain001 Examples

Runnable, self-checking examples covering **every Pain001 feature**. Each
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
| `10_input_formats.py` | Loading the same data from CSV, SQLite, JSON, and JSON Lines |
| `11_observability_metrics.py` | Metric callbacks (`register_metrics_callback`) for Prometheus/OpenTelemetry/log forwarding |
| `12_mcp_tools.py` | The MCP server's tools called directly (run the server with `pain001-mcp`; requires `pip install pain001[mcp]`) |
| `13_lsp_diagnostics.py` | The LSP diagnostic engine linting a CSV for bad IBAN/BIC/currency/charset and missing columns (editor server: `pain001-lsp`, `pip install pain001[lsp]`) |
| `14_redis_distributed.py` | v0.0.53 Redis-backed durable job store (`RedisJobStore`) + cross-replica rate limiter (`RedisFixedWindowBackend`); fakeredis-driven so the script runs without a Redis daemon (requires `pip install pain001[redis]`) |
| `15_example_corpus.py` | The example corpus: read API and coverage manifest, schema inventory and coverage of your own file, synthetic identifiers, building a scenario with an illustrative private overlay, the four-rung ladder and rail projection, ISO external code sets, the guideline derive tool on a synthetic guideline outside the repository, and `pain.008.001.08` generation |
| `16_iso_json_twins.py` | The ISO JSON twin of a corpus file (RA 2025 convention), validation against the per-edition JSON Schema, editing in JSON and encoding back through the XSD, the schema rejecting a bad decimal, and the records twin with its measured gap and regeneration through the CSV pipeline |

Together these scripts exercise generation (all message types), every
input format, the CLI suite, the REST API, scheme validation, the parsers,
version migration, streaming, observability, the MCP tools, the LSP
diagnostic engine, and the example corpus engine — i.e. the full public
feature surface.

Sample inputs live in `data/`: `payments.csv` (a copy of the bundled
`pain001/templates/pain.001.001.03/template.csv`, used by the CLI and
library examples) and `payments.json` (typed values for the REST API,
whose validation expects native JSON integers and booleans).
