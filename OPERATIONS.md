<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Operating Pain001

A runbook for running the Pain001 REST API in production: configuration,
observability, scaling, and common incidents. The library and CLI are
stateless and need none of this; it applies to the `pain001[api]` server.

## Running the server

```bash
pip install "pain001[api]"
pain001 serve                                  # dev: 127.0.0.1:8000, no key needed
# Any other address needs a key (or an explicit opt-out, below).
export PAIN001_API_KEY=$(openssl rand -hex 32)
pain001 serve --host 0.0.0.0 --port 8000
# Production: front with a process manager / container + a reverse proxy.
uvicorn pain001.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

`pain001 serve` refuses to bind anything but loopback (`127.0.0.1`,
`::1`, `localhost`) while `PAIN001_API_KEY` is unset, because the API
then has no authentication. It exits with a usage error naming the two
ways out: set `PAIN001_API_KEY`, or, for a local experiment on a
network you trust, pass `--insecure` (or set `PAIN001_ALLOW_INSECURE=1`)
to serve unauthenticated anyway:

```bash
# Local experiments only: anyone who can reach the port can use the API.
pain001 serve --host 0.0.0.0 --insecure
```

`uvicorn` started directly cannot apply this check (the application
does not see the address it is bound to); it logs a start-up warning
instead when `PAIN001_API_KEY` is unset, so set the key whenever you
run it on anything but loopback.

Validation and generation run in a thread pool, off the event loop, so
`/health` and other requests stay responsive while a large file is
processed. At most `PAIN001_API_CONCURRENCY` pipelines run at once per
worker process (default: the CPU count); further requests and async
jobs wait their turn (jobs show `pending` until they start). With
`--workers N`, each worker has its own pool.

### Container image (GHCR)

```bash
# Pull a tagged release (or :latest from main); replace <version>.
docker pull ghcr.io/sebastienrousseau/pain001:<version>

# Run the REST API.
docker run --rm -p 8000:8000 \
  -e PAIN001_API_KEY=$(openssl rand -hex 32) \
  ghcr.io/sebastienrousseau/pain001:<version> \
  serve --host 0.0.0.0 --port 8000
```

The image is multi-arch (`linux/amd64`, `linux/arm64`), runs as a
non-root `pain001` user, declares a HEALTHCHECK, and ships the `[api]`
extra preinstalled. Every release pushes a matching tag to GHCR. The
image does not include the `redis`, `otel` or other optional extras;
build your own image from `pain001[api,redis]` (and so on) when you need
them.

## Interactive API reference

The OpenAPI schema is hosted as an interactive
[Scalar](https://scalar.com) page on the docs site:

- **<https://sebastienrousseau.github.io/pain001/api-reference.html>**

The same page is reachable on a running server at `/api/reference`,
and the raw OpenAPI document is at `/openapi.json`. The hosted page
is rebuilt from `main` by the `docs.yml` workflow when the docs, the
package version or the dependencies change, so it can lag an API
change on `main`. A running server always serves its own schema.

## Configuration

All operational controls are environment variables. Unset, there is
no authentication, no rate limit, an in-memory job store and the
browser dashboard at `/api/v1/ui` is on, so local runs need no setup.

| Variable | Effect | Example |
| :--- | :--- | :--- |
| `PAIN001_API_KEY` | Require `Authorization: Bearer <key>` on every endpoint except `/api/v1/health` and `/api/v1/ready`, `/metrics` included; `pain001 serve` needs it for any non-loopback `--host` | `export PAIN001_API_KEY=$(openssl rand -hex 32)` |
| `PAIN001_METRICS_TOKEN` | A separate bearer token for `/metrics`, so the scraper never holds the API key; when set, `/metrics` takes this token and not the key | `export PAIN001_METRICS_TOKEN=$(openssl rand -hex 32)` |
| `PAIN001_METRICS_PAYMENT_VOLUME` | `1`, `true` or `yes` records and exposes `pain001_payment_volume_cents_total`; off by default because volume per currency is business data | `1` |
| `PAIN001_MAX_BODY_BYTES` | Largest request body; a bigger one is answered `413` before it is parsed. A positive integer; anything else stops the server at start-up | `22020096` (21 MiB, default) |
| `PAIN001_MAX_ACTIVE_JOBS` | Async jobs that may be pending or processing at once; `POST /generate/async` answers `503` with `Retry-After: 5` beyond it | `100` (default) |
| `PAIN001_ALLOW_INSECURE` | `1`, `true` or `yes` lets `pain001 serve` bind a non-loopback address without a key (same as `--insecure`); local experiments only | `1` |
| `PAIN001_API_CONCURRENCY` | Validation and generation pipelines run at once per worker process; extra requests and jobs queue. A positive integer; anything else stops the server at start-up | CPU count (default) |
| `PAIN001_RATE_LIMIT` | Per-client request cap (fixed window); unset means no limit | `100/minute` |
| `PAIN001_RATE_LIMIT_BACKEND` | `redis` shares the rate-limit counters across replicas (`pain001[redis]`) | `redis` |
| `PAIN001_RATE_LIMIT_REDIS_URL` | Redis URL for the rate limiter; falls back to `PAIN001_JOB_STORE_URL` | `redis://redis:6379/0` |
| `PAIN001_TRUSTED_PROXIES` | Comma-separated addresses or networks of the reverse proxies in front of the API. Only when the connecting peer is one of them does the rate limiter read the forwarded header, keying on the right-most hop that is not a trusted proxy. Empty (default): the socket address is the key and forwarded headers are ignored. An entry that is not an address or network stops start-up | `10.0.0.0/8` |
| `PAIN001_FORWARDED_HEADER` | The one header those proxies write: `x-forwarded-for` (default) or `forwarded` (RFC 7239). Pick the header your proxy sets, never one it passes through untouched | `x-forwarded-for` |
| `PAIN001_JOB_STORE_DIR` | Persist async jobs to disk so they survive restarts | `/var/lib/pain001/jobs` |
| `PAIN001_JOB_STORE_URL` | Store async jobs in Redis for multi-replica deployments (`pain001[redis]`); takes precedence over `PAIN001_JOB_STORE_DIR` | `redis://redis:6379/1` |
| `PAIN001_JOB_STORE_NAMESPACE` | Key prefix for the Redis job store | `pain001:jobs` (default) |
| `PAIN001_UI_DISABLED` | `1`, `true` or `yes` takes the `/api/v1/ui` dashboard offline | `1` |
| `PAIN001_DISABLE_PLUGINS` | Comma-separated plugin names to skip | `xlsx,gpg` |
| `OTEL_ENABLED` | Turn on OpenTelemetry tracing (`pain001[otel]`): a server span per request, parented on an inbound `traceparent` (see [Request ids and traces](#request-ids-and-traces)) | `true` |

## Health and readiness

- `GET /api/v1/health` → `{"status":"healthy","version":"…"}`. Use it as the
  liveness probe: it answers while the process can serve HTTP and checks
  nothing else. Any non-200 or timeout = unhealthy.
- `GET /api/v1/ready` → `{"status":"ready","checks":{…}}`, or `503` with
  `"status":"not_ready"`. It loads every bundled template and XSD (once,
  then remembered) and, when a job store is configured, pings it (the
  directory is writable, or Redis answers). `checks` names each result
  (`ok`, `failed`, or `disabled` when there is no store); the reason for a
  failure is logged, not returned. Use it as the readiness probe and the
  load balancer check. Neither endpoint takes the API key.

```yaml
# Kubernetes probes
livenessProbe:
  httpGet: { path: /api/v1/health, port: 8000 }
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /api/v1/ready, port: 8000 }
  periodSeconds: 10
```

## Metrics (Prometheus)

`GET /metrics` exposes the Prometheus text format (no extra dependency).
With `PAIN001_API_KEY` set it needs `Authorization: Bearer <key>`, or the
`PAIN001_METRICS_TOKEN` when that is set:

| Metric | Type | Meaning |
| :--- | :--- | :--- |
| `pain001_build_info{version}` | gauge | Running version (always 1) |
| `pain001_supported_message_types` | gauge | Number of ISO 20022 types served |
| `pain001_scheme_profiles` | gauge | Registered scheme rulebooks |
| `pain001_jobs{status}` | gauge | Async jobs by status (pending/processing/success/failed/cancelled) |
| `pain001_http_requests_total{method,status}` | counter | HTTP requests seen |
| `pain001_files_processed_total{status,message_type}` | counter | Files processed, by outcome and message type |
| `pain001_payment_volume_cents_total{currency}` | counter | Payment volume in minor units, by currency; only with `PAIN001_METRICS_PAYMENT_VOLUME=1` |
| `pain001_processing_seconds` | summary | Generation processing latency |

Scrape config:

```yaml
scrape_configs:
  - job_name: pain001
    metrics_path: /metrics
    authorization:
      credentials_file: /etc/prometheus/pain001-metrics-token
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

Structured JSON logging with PII redaction is available in
`pain001.logging_schema`; the server does not turn it on by itself, so call
`configure_json_logging()` from your own entry point when you want JSON.
Ship stdout to your log pipeline.

### Request ids and traces

Every response carries `X-Request-ID`. A caller's own id is echoed when it
is 1 to 128 characters of letters, digits and `. _ : -`, starting with a
letter or digit; anything else is replaced by a fresh `req-<8 hex>` id.
JSON log lines written while serving the request carry it as `request_id`,
so a client can quote the id from a failed answer and you can find its
logs. A proxy that stamps its own id (nginx `$request_id`) can pass it on.

An inbound W3C `traceparent` joins the request to the caller's trace. With
`OTEL_ENABLED=true` and the `otel` extra, each request gets a server span
(`GET /api/v1/status/{job_id}`, with the status code and route) whose
parent is the caller's span, and the handler spans (`pain001.api.*`) are
its children; log lines carry its `trace_id` and `span_id`. Without
tracing, logs still carry the caller's `trace_id`. If the host process has
already set an OpenTelemetry tracer provider, pain001 uses it rather than
installing its own, so embedding pain001 keeps the host's exporter and
sampler. Propagators follow `OTEL_PROPAGATORS` (W3C trace context and
baggage by default).

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
