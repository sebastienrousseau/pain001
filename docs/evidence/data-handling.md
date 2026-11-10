<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Data handling

Pain001 is a library and a set of commands that run on your own
infrastructure. There is no hosted Pain001 service, no account and no
telemetry. This page says exactly when the software opens a network
connection, so a reviewer can check each statement against the code.

## What Pain001 does not do

- **No hosted service.** The project runs no server that receives your
  payment files. Generating, validating and checking files happen in
  your process.
- **No telemetry.** Nothing reports usage, errors or file contents to
  the project. The only tracing support is the opt-in OpenTelemetry
  integration described below, which sends spans only to an endpoint you
  configure.
- **No schema downloads.** XSD validation uses the schemas bundled in
  the package. The `lxml` parser runs with entity resolution, DTD loading
  and network access switched off
  ([`pain001/xml/validate_via_xsd.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/xml/validate_via_xsd.py)).

## When Pain001 opens a network connection

Each case needs an optional extra, an explicit command or explicit
configuration. None is on by default.

| Case | What connects, and to where | Needs |
| :--- | :--- | :--- |
| `pain001 upload` | An SFTP connection to the host you name, after its host key is checked and before any credential is sent ([`pain001/transport/sftp.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/transport/sftp.py)) | the `upload` extra and the command |
| `pain001 download` | The same SFTP session, to fetch replies from the host you name ([ADR 0013](../adr/0013-download-replies-exactly-once.md)) | the `upload` extra and the command |
| `pain001 serve` | Listens for HTTP requests (it does not connect out). Without `PAIN001_API_KEY` it refuses to bind anything but loopback unless you pass `--insecure` ([`pain001/cli/_serve.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/cli/_serve.py)) | the `api` extra and the command |
| REST job store or rate limiter on Redis | Connects to the Redis URL you set in `PAIN001_JOB_STORE_URL`, or with `PAIN001_RATE_LIMIT_BACKEND=redis` to `PAIN001_RATE_LIMIT_REDIS_URL` ([`job_store.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/api/job_store.py), [`ratelimit.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/api/ratelimit.py)) | the `redis` extra and that setting |
| OpenTelemetry tracing | Exports spans over OTLP/HTTP to the endpoint in the standard `OTEL_EXPORTER_OTLP_*` variables ([`pain001/observability/otel.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/observability/otel.py)) | the `otel` extra, `OTEL_ENABLED` and an exporter endpoint |

The MCP server (`pain001 mcp`) talks to its client over standard input
and output; it opens no network port and makes no outbound connection
([`pain001/mcp/server.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/mcp/server.py)).
MCP and REST never fetch or send files over SFTP: `download` is a
command-line and library feature only ([ADR 0013](../adr/0013-download-replies-exactly-once.md)).

## Data at rest

- Pain001 writes only what you ask for: generated XML, reports, and
  files `download` saves to the directory you name.
- `pain001 download` keeps a local SQLite ledger (file mode 0600) of the
  remote paths it fetched and where it saved them. The ledger holds no
  file contents and no credentials.
- The REST API keeps job state in memory by default, or on disk or in
  Redis when you configure it to.
- Structured logs redact IBAN, BIC and name fields by default
  ([`pain001/logging_schema/redaction.py`](https://github.com/sebastienrousseau/pain001/blob/main/pain001/logging_schema/redaction.py)),
  and validation errors carry the rule and field, not the value.

## How to check this yourself

```bash
# Network clients appear only in the opt-in transport, API and tracing code
grep -rlE 'import (socket|paramiko|redis)|from (paramiko|redis)|urlopen|httpx|aiohttp|OTLPSpanExporter' pain001/
```

The expected result is files under `pain001/transport/`, `pain001/api/`
and `pain001/observability/` only.
