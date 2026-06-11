# Pain001 Examples

Runnable, self-checking examples for the headline workflows. Each
script exits `0` on success and is executed in CI by
`tests/test_examples.py`, so they cannot silently drift out of date.

Run them from the repository root:

```bash
python examples/01_generate_xml_file.py
```

| Example | Shows |
|---|---|
| `01_generate_xml_file.py` | Library API: load CSV, render the bundled template, XSD-validate, write the XML file |
| `02_generate_xml_string.py` | In-memory `generate_xml_string` for APIs, serverless, and queues |
| `03_cli_workflows.py` | CLI dry-run, generation, and the documented exit codes (0 and 2) |
| `04_config_profiles.py` | Built-in configuration profiles via `ConfigManager` |
| `05_api_job_lifecycle.py` | REST API: health, sync validation, async job submit/poll/download, `DELETE /api/jobs/{id}` (requires `pip install pain001[api]`) |

Sample inputs live in `data/`: `payments.csv` (a copy of the bundled
`pain001/templates/pain.001.001.03/template.csv`, used by the CLI and
library examples) and `payments.json` (typed values for the REST API,
whose validation expects native JSON integers and booleans).
