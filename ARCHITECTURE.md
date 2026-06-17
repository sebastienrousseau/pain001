<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Pain001 Architecture

A map of the codebase for new contributors and maintainers. The goal is
that anyone can navigate, extend, and reason about Pain001 without prior
context — reducing reliance on any single person.

## The pipeline

Generation flows left to right; each stage is a separate, testable unit:

```
input file / list[dict]
        │  data/loader.py            (dispatch by extension)
        ▼
   csv/ · db/ · json/ · parquet/     (per-format loaders + streaming)
        │  → list[dict] payment rows
        ▼
   validation/                       (schema_validator, csv/db validators,
        │                             iban/bic, charset, schemes)
        ▼
   xml/message_registry.py           (per-version field preparation)
        │
        ▼
   xml/generate_xml.py               (Jinja2 render of templates/<type>/)
        │
        ▼
   xml/validate_via_xsd.py           (mandatory XSD validation, defusedxml)
        │
        ▼
   xml/write_xml_to_file.py  ──or──  generate_xml_string()  (in-memory)
```

## Module map

| Area | Module(s) | Responsibility |
| :--- | :--- | :--- |
| **Entry points** | `__main__.py`, `cli/cli.py`, `api/app.py`, `mcp/server.py`, `core/core.py` | CLI command group (`generate`/`validate`/`versions`/`inspect`/`init`/`serve`/`mcp`, with bare flags routed to `generate`), REST API, MCP server, and the `process_files` / `process_files_streaming` library API |
| **Input** | `data/loader.py` + `csv/`, `db/`, `json/`, `parquet/` | Unified extension-dispatch loader and per-format readers (batch + streaming) |
| **Validation** | `validation/` | `schema_validator` (XSD-field types), `iban_validator`, `bic_validator`, `charset` (ISO 20022 Latin set), `schemes` (scheme rulebooks), `service` (orchestrator) |
| **Generation** | `xml/` | `message_registry` (per-version data prep), `generate_xml`, `create_root_element`, `validate_via_xsd`, `write_xml_to_file` |
| **Templates** | `templates/` | `registry` (`TemplateMetadata`), `guardrails` (template/XSD drift checks); bundled assets under `templates/<message_type>/` |
| **Migration** | `migration/version_mapper.py`, `migrate.py` | Map payment data between pain.001 versions via YAML mappings |
| **Parsers / builders** | `pain002/`, `camt053/` | Read bank responses (status reports, statements) into dicts; `pain002/generator.py` also *builds* pain.002 reports (round-trips with the parser) |
| **API** | `api/app.py`, `api/models.py`, `api/job_manager.py`, `api/job_store.py`, `api/ratelimit.py`, `api/metrics.py` | FastAPI app (routes mounted under `/api/v1` with a hidden `/api` legacy alias), pydantic models, async job manager with an optional durable file store, an in-process rate-limit middleware, and a dependency-free Prometheus `/metrics` exporter |
| **MCP** | `mcp/server.py` | FastMCP server (stdio) exposing generation/validation as tools, the XSD set as resources, and a guided prompt — thin adapters over the core, taking inline rows |
| **LSP** | `lsp/diagnostics.py`, `lsp/server.py` | A dependency-free CSV diagnostic engine (IBAN/BIC/currency/charset, required columns) and a `pygls` stdio language server that feeds it to editors; VS Code client under `editors/vscode/` |
| **Config** | `config/manager.py` | Layered configuration (CLI args, file, profiles) |
| **Observability** | `logging_schema/` (package), `observability/` | Structured JSON logging with PII redaction; metric callbacks + OpenTelemetry trace context |
| **Security** | `security/path_validator.py` | Path-traversal-safe path validation (CWE-22) |
| **Async** | `async_adapter.py` | `asyncio.to_thread` wrappers over the sync API |
| **Shared** | `constants.py`, `exceptions.py` | Version, valid message types, paths; the exception hierarchy |

## Key design decisions

- **Registry-driven generation.** Each message type has a `MessageDefinition`
  in `xml/message_registry.py` and a bundled `templates/<type>/` directory.
  There is no per-version code duplication.
- **Money is `Decimal` end to end.** `NbOfTxs` and `CtrlSum` are always
  computed from the rows, never trusted from input.
- **XSD validation is mandatory** and routed through `defusedxml` (XXE /
  entity-expansion safe). Output that does not validate is never written
  as a success.
- **Scheme validation is a pluggable layer** on top of XSD: a
  `ValidationProfile` returns structured, per-row `SchemeViolation`s.
- **Coverage is enforced at 98%**; only entry-point guards and genuinely
  defensive barriers are excluded (`# pragma: no cover`), never padded
  with fake tests.

## Extension points

- **Add a message type:** drop a `templates/<type>/` bundle (template,
  XSD, metadata) and register a `MessageDefinition` in
  `xml/message_registry.py`. Add a version entry to `constants.py`.
- **Add a scheme profile:** subclass `ValidationProfile` in
  `validation/schemes.py`, register it in `PROFILES`, and add remediation
  text to `REMEDIATIONS`. (See `SCHEMES.md`.)
- **Add an input format:** add a loader under the appropriate package and
  register its extension in `data/loader.py`.

## Where to look first

- Runnable, per-feature examples: [`examples/`](examples/).
- Editor extension client: [`editors/vscode/`](editors/vscode/).
- Scheme rule catalogue: [`SCHEMES.md`](SCHEMES.md).
- Release process: [`RELEASING.md`](RELEASING.md).
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).
