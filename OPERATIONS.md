<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Operating Pain001

A runbook for running the Pain001 REST API in production: configuration,
observability, scaling, and common incidents. The library and CLI are
stateless and need none of this; it applies to the `pain001[api]` server.

## Running the server

```bash
pip install "pain001[api]"
pain001 serve --host 0.0.0.0 --port 8000      # dev
# Production: front with a process manager / container + a reverse proxy.
uvicorn pain001.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration

All operational controls are environment variables; all are **off by
default** so local runs need no setup.

| Variable | Effect | Example |
| :--- | :--- | :--- |
| `PAIN001_API_KEY` | Require `Authorization: Bearer <key>` on every endpoint | `export PAIN001_API_KEY=$(openssl rand -hex 32)` |
| `PAIN001_RATE_LIMIT` | Per-client request cap (in-process, fixed window) | `100/minute` |
| `PAIN001_JOB_STORE_DIR` | Persist async jobs to disk so they survive restarts | `/var/lib/pain001/jobs` |

## Health and readiness

- `GET /api/v1/health` → `{"status":"healthy","version":"…"}`. Use it as the
  liveness/readiness probe. Any non-200 or timeout = unhealthy.

```yaml
# Kubernetes probe
livenessProbe:
  httpGet: { path: /api/v1/health, port: 8000 }
  periodSeconds: 10
```

## Metrics (Prometheus)

`GET /metrics` exposes the Prometheus text format (no extra dependency):

| Metric | Type | Meaning |
| :--- | :--- | :--- |
| `pain001_build_info{version}` | gauge | Running version (always 1) |
| `pain001_supported_message_types` | gauge | Number of ISO 20022 types served |
| `pain001_scheme_profiles` | gauge | Registered scheme rulebooks |
| `pain001_jobs{status}` | gauge | Async jobs by status (pending/processing/success/failed/cancelled) |
| `pain001_http_requests_total{method,status}` | counter | HTTP requests seen |

Scrape config:

```yaml
scrape_configs:
  - job_name: pain001
    metrics_path: /metrics
    static_configs:
      - targets: ["pain001:8000"]
```

Useful queries / panels:

- **Request rate:** `sum by (status) (rate(pain001_http_requests_total[5m]))`
- **Error ratio:** `sum(rate(pain001_http_requests_total{status=~"5.."}[5m]))
  / sum(rate(pain001_http_requests_total[5m]))`
- **Failed jobs:** `pain001_jobs{status="failed"}`

Suggested alerts:

- `5xx ratio > 1% for 5m` → page.
- `pain001_jobs{status="failed"}` rising → investigate input data / schemas.
- Health probe failing → restart / roll back.

> The metrics and rate limiter are **single-process**. Behind multiple
> workers/replicas, scrape each instance (Prometheus handles aggregation)
> and enforce hard rate limits at the gateway or with a shared store.

## Logs

Structured JSON logging with PII redaction is built in
(`pain001.logging_schema`). Ship stdout to your log pipeline; correlate with
traces via the OpenTelemetry context attached to metric events when an OTel
SDK is present.

## Scaling notes

- The API is stateless **except** for async jobs. For multiple replicas,
  set `PAIN001_JOB_STORE_DIR` to shared storage, or treat async generation
  as node-local and route a job's status/download to the node that owns it.
- Generation is CPU-bound (XML render + XSD validation); scale with workers
  /replicas and put a queue in front for large batches.

## Common incidents

| Symptom | Likely cause | Action |
| :--- | :--- | :--- |
| `401 Invalid or missing API key` | `PAIN001_API_KEY` set, client not sending bearer | Send `Authorization: Bearer <key>` |
| `429 Rate limit exceeded` | `PAIN001_RATE_LIMIT` too low for traffic | Raise the limit or move it to the gateway |
| `400` on generate with `scheme_violations` | Data breaks a scheme rulebook | See [SCHEMES.md](SCHEMES.md); fix the data |
| Jobs lost after restart | In-memory job store | Set `PAIN001_JOB_STORE_DIR` |
| `500` on a valid request | Unexpected error (logged) | Check JSON logs; open an issue with the trace id |

## Releasing

See [RELEASING.md](RELEASING.md) for the cut/publish process and
[GOVERNANCE.md](GOVERNANCE.md) for who has release authority.
