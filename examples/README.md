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
| `06_scheme_validation.py` | Scheme rulebook validation — `sepa-sct`, `sepa-sdd`, `sepa-inst`, structured violations + remediation, and the ISO 20022 charset guard |
| `07_parse_bank_responses.py` | Parsing the messages banks send back: `pain.002` status reports and `camt.053` statements |
| `08_version_migration.py` | Mapping payment data between pain.001 versions with `VersionMapper` |
| `09_streaming_large_batch.py` | Streaming generation: one validated XML file per input chunk |
| `10_input_formats.py` | Loading the same data from CSV, SQLite, JSON, and JSON Lines |
| `11_observability_metrics.py` | Metric callbacks (`register_metrics_callback`) for Prometheus/OpenTelemetry/log forwarding |
| `12_mcp_tools.py` | The MCP server's tools called directly (run the server with `pain001-mcp`; requires `pip install pain001[mcp]`) |
| `13_lsp_diagnostics.py` | The LSP diagnostic engine linting a CSV for bad IBAN/BIC/currency/charset and missing columns (editor server: `pain001-lsp`, `pip install pain001[lsp]`) |

Together these scripts exercise generation (all message types), every
input format, the CLI suite, the REST API, scheme validation, the parsers,
version migration, streaming, observability, the MCP tools, and the LSP
diagnostic engine — i.e. the full public feature surface.

Sample inputs live in `data/`: `payments.csv` (a copy of the bundled
`pain001/templates/pain.001.001.03/template.csv`, used by the CLI and
library examples) and `payments.json` (typed values for the REST API,
whose validation expects native JSON integers and booleans).
