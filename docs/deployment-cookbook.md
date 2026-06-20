<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Deployment cookbook: pain001 in production

This is the **opinionated, copy-pasteable** deployment guide for
running pain001's REST API in production with the v0.0.53 stack:
distributed rate limiting, durable jobs, metrics, dashboards, TLS
termination, log aggregation. If you want to know *how* to run
pain001 reliably and don't want to make a hundred small decisions,
start here.

For the *reference* (every env var, every endpoint, every metric),
see [OPERATIONS.md](../OPERATIONS.md). This document is the recipe;
that one is the spec.

## Contents

- [Architecture](#architecture) — what you're about to deploy, in one diagram
- [Quick deploy (single host)](#quick-deploy-single-host) — 10 minutes to a running stack
- [Configuration](#configuration) — every knob you need to turn
- [Operating the stack](#operating-the-stack) — logs, restarts, upgrades, rollback
- [Scaling out](#scaling-out) — when to go multi-replica
- [HA + DR](#ha--dr) — the path to 99.9% uptime
- [Hardening](#hardening) — the production checklist
- [Cost notes](#cost-notes) — what this actually costs to run

---

## Architecture

```
                  Internet
                     |
                     v
            +-----------------+
            |  nginx (TLS)    |  443 -> 8000
            |  reverse proxy  |
            +--------+--------+
                     |
                     v
            +-----------------+        +-------------------+
            |  pain001 :api   |<------>|  Redis            |
            |  (REST)         |        |  - rate limiter   |
            |                 |        |  - job store      |
            +--------+--------+        +-------------------+
                     |
        Prometheus scrape :8000/metrics
                     |
                     v
            +-----------------+        +-------------------+
            |  Prometheus     |------->|  Grafana          |
            |  (15-day TSDB)  |        |  (pre-loaded      |
            +-----------------+        |   pain001 board)  |
                                       +-------------------+
```

Five containers. Single host. Survives a Docker daemon restart.
Add a second pain001 replica to scale; everything else stays
single-instance until you genuinely need HA (see [HA + DR](#ha--dr)).

---

## Quick deploy (single host)

### Prereqs

- A Linux host with Docker 24+ and Docker Compose v2.
- 2 vCPU / 4 GB RAM minimum (production: 4 vCPU / 8 GB recommended).
- A domain name (`payments.example.com`) pointed at the host.
- Ports 80 + 443 open to the internet, **8000 / 6379 / 9090 / 3000
  closed** to everything except localhost.

### File layout

```
/opt/pain001/
├── docker-compose.yml
├── .env                       # secrets, never commit
├── nginx/
│   ├── nginx.conf
│   └── tls/                   # certs from your ACME client
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml
│       └── dashboards/
│           └── pain001.json   # pre-built dashboard
└── data/                      # persistent volumes mount here
    ├── redis/
    ├── prometheus/
    └── grafana/
```

### `docker-compose.yml`

```yaml
services:
  pain001:
    image: ghcr.io/sebastienrousseau/pain001:0.0.53
    restart: unless-stopped
    expose:
      - "8000"
    environment:
      # Required
      PAIN001_API_KEY: ${PAIN001_API_KEY}

      # Rate limiting (Redis-backed, shared across replicas)
      PAIN001_RATE_LIMIT: "100/minute"
      PAIN001_RATE_LIMIT_BACKEND: redis
      PAIN001_RATE_LIMIT_REDIS_URL: redis://redis:6379/0

      # Durable job store (Redis-backed, survives restarts)
      PAIN001_JOB_STORE_URL: redis://redis:6379/1

      # Logging
      PYTHONUNBUFFERED: "1"
    command: >
      serve --host 0.0.0.0 --port 8000
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/api/v1/health\", timeout=5)'"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: >
      redis-server
        --appendonly yes
        --maxmemory 512mb
        --maxmemory-policy allkeys-lru
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/tls:/etc/nginx/tls:ro
    depends_on:
      pain001:
        condition: service_healthy

  prometheus:
    image: prom/prometheus:v3.0.1
    restart: unless-stopped
    expose:
      - "9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./data/prometheus:/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.retention.time=15d
      - --web.enable-lifecycle

  grafana:
    image: grafana/grafana:11.3.0
    restart: unless-stopped
    expose:
      - "3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./data/grafana:/var/lib/grafana
    depends_on:
      - prometheus
```

### `.env`

```bash
# Long random string. Generate with: openssl rand -hex 32
PAIN001_API_KEY=<your-bearer-token>
GRAFANA_ADMIN_PASSWORD=<grafana-admin-password>
```

Mode `0600`, never committed.

### `nginx/nginx.conf`

```nginx
events { worker_connections 1024; }

http {
  # TLS termination + rate-limit at the edge (defence in depth alongside
  # pain001's own limiter).
  limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

  upstream pain001 {
    server pain001:8000;
    keepalive 16;
  }

  # HTTPS-only; redirect HTTP -> HTTPS.
  server {
    listen 80;
    server_name payments.example.com;
    return 301 https://$host$request_uri;
  }

  server {
    listen 443 ssl http2;
    server_name payments.example.com;

    ssl_certificate     /etc/nginx/tls/fullchain.pem;
    ssl_certificate_key /etc/nginx/tls/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # HSTS (only after you're sure TLS is solid)
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;

    # API + docs
    location /api/ {
      limit_req zone=api burst=50 nodelay;
      proxy_pass         http://pain001;
      proxy_http_version 1.1;
      proxy_set_header   Host $host;
      proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header   X-Forwarded-Proto $scheme;
      proxy_read_timeout 120s;
    }

    # Metrics: NOT exposed publicly. Comment out if Prometheus scrapes
    # over the docker network only (recommended).
    # location /metrics { ... }
  }
}
```

### `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: pain001
    static_configs:
      - targets: ["pain001:8000"]
    metrics_path: /metrics
```

### `grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

### Boot

```bash
cd /opt/pain001
docker compose pull
docker compose up -d
docker compose ps
```

Wait for `pain001` to report `healthy`. Verify:

```bash
curl -sS https://payments.example.com/api/v1/health
# {"status":"ok","version":"0.0.53"}
```

That's the production deployment. Five containers, one host, full
observability.

---

## Configuration

### Required env vars

| Variable | Purpose |
| :--- | :--- |
| `PAIN001_API_KEY` | Bearer token required on every `/api/v1/*` request. Generate with `openssl rand -hex 32`; rotate every 90 days. |

### Recommended env vars

| Variable | Recommended value | Why |
| :--- | :--- | :--- |
| `PAIN001_RATE_LIMIT` | `100/minute` | Per-client cap. Tune to your traffic; the in-process default is too low for any real workload. |
| `PAIN001_RATE_LIMIT_BACKEND` | `redis` | Shared across replicas. The in-process default protects one worker only. |
| `PAIN001_RATE_LIMIT_REDIS_URL` | `redis://redis:6379/0` | Pointing at the compose-network Redis. |
| `PAIN001_JOB_STORE_URL` | `redis://redis:6379/1` | Durable async-job state. Survives a pain001 restart. |
| `PAIN001_JOB_STORE_DIR` | _unset_ when using Redis | The file-backed store is an alternative, not an addition. |

### Optional / scenario env vars

| Variable | When to set | Effect |
| :--- | :--- | :--- |
| `PAIN001_OUTPUT_DIR_ALLOWLIST` | If your callers specify `output_dir` per request | Comma-separated list of permitted output directories. Defaults to cwd + tmp. |
| `PYTHONUNBUFFERED` | Always in containers | `print()` lines flush immediately. Critical for `docker logs` debugging. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Wiring to Datadog / Honeycomb / Tempo | OpenTelemetry traces ship to the named OTLP collector. (Tracing is opt-in in v0.0.54; see issue [#182](https://github.com/sebastienrousseau/pain001/issues/182).) |

---

## Operating the stack

### Logs

```bash
# Live tail of pain001
docker compose logs -f pain001

# Last 1000 lines, with timestamps
docker compose logs --timestamps --tail 1000 pain001

# Everything since 1 hour ago, across all services
docker compose logs --since 1h
```

For production, ship logs to an aggregator (Loki / Datadog / CloudWatch).
Pain001 emits structured JSON when `PAIN001_LOG_JSON=1`.

### Health + readiness

```bash
# Liveness (pain001 process is alive)
curl -sS https://payments.example.com/api/v1/health

# Readiness (Redis reachable, schema cache loaded)
curl -sS https://payments.example.com/api/v1/ready

# Metrics (only over docker network; not exposed via nginx)
docker compose exec pain001 wget -qO- http://localhost:8000/metrics | head -40
```

Add the readiness probe to your load balancer health check.

### Upgrades

```bash
# 1. Pin the new version in docker-compose.yml.
$EDITOR docker-compose.yml   # bump :0.0.53 -> :0.0.54

# 2. Pull + recreate in place. Zero downtime for a single replica
#    requires a second replica behind nginx; see Scaling out.
docker compose pull pain001
docker compose up -d pain001

# 3. Verify.
curl -sS https://payments.example.com/api/v1/health | jq .version
docker compose logs --since 5m pain001 | grep -iE "error|warn"
```

### Rollback

```bash
# Revert the image tag in docker-compose.yml and recreate.
$EDITOR docker-compose.yml   # 0.0.54 -> 0.0.53
docker compose up -d pain001
```

Pain001 has been backwards-compatible on the v0.0.x line; rollback
across a minor is always safe. Redis-stored job state is JSON, no
schema migrations.

### Backup

The only stateful service is Redis. The compose stack mounts
`./data/redis` — back that directory up nightly.

```bash
# Snapshot:
docker compose exec redis redis-cli BGSAVE
# Wait, then archive:
tar czf "redis-$(date +%F).tgz" data/redis/
```

For point-in-time recovery, enable AOF (`--appendonly yes` is
already on) + ship the AOF file to S3 every 5 min via a sidecar.

---

## Scaling out

The compose above handles ~50 req/s sustained on a 4 vCPU host.
When you outgrow that:

### Add pain001 replicas (single host)

```yaml
services:
  pain001:
    # ... as before ...
    deploy:
      replicas: 4
```

Nginx's `upstream pain001 { server pain001:8000 }` already
round-robins. Redis-backed rate limiting + job store mean replicas
share state correctly.

### Add pain001 replicas (multi host)

Move from Compose to Kubernetes / Nomad. The image, env vars, and
health probes carry over unchanged. Run Redis as a clustered
service (Elasticache, Redis Enterprise, or a HA setup with
Sentinel). Run nginx (or an ingress controller) in HA mode.

### Bottleneck order (in practice)

1. **Network egress** (the XML you generate goes somewhere). Cap is
   usually your bank's API throughput, not yours.
2. **Redis CPU** for high request volumes — the rate limiter is
   write-heavy. Scale Redis vertically first, cluster only if you
   exceed ~50k req/s.
3. **Pain001 CPU** (Jinja2 template rendering + XSD validation).
   Add replicas.
4. **XSD validation memory** when batches > 100k rows. Use streaming
   mode (`--streaming --chunk-size 1000`).

---

## HA + DR

The single-host compose stack is **not HA**. Loss of the host means
loss of the service until you reprovision.

For 99.9% uptime (~9 hours/year downtime):

| Component | HA setup |
| :--- | :--- |
| pain001 | ≥ 2 replicas on ≥ 2 hosts, behind a HA load balancer |
| Redis | Sentinel-managed primary + 2 replicas, OR Elasticache cluster mode |
| nginx | 2 instances behind an L4 LB (e.g. AWS NLB, Cloudflare Load Balancer) |
| Prometheus | Federated; pair with Thanos / Mimir for HA |
| Grafana | Stateless when datasources + dashboards are provisioned from disk; ≥ 2 replicas |

For 99.99% uptime (~52 minutes/year): multi-region active/active
with bank-side failover. Beyond the scope of this cookbook —
talk to your bank about their availability story.

**Disaster recovery (DR)**: nightly off-site backup of `data/redis`
+ the compose stack itself (kept in git). Recovery time objective
(RTO): provision new host + restore Redis snapshot = ~1 hour for
the runbook-prepared. Recovery point objective (RPO): 24 hours
(nightly backup) or 5 minutes (AOF shipped to S3 continuously).

---

## Hardening

### TLS

- Use [Let's Encrypt + certbot](https://certbot.eff.org/) or your
  cloud's managed cert. Renewal is automatic; pain001 never sees a
  cert.
- HSTS only after a successful month on TLS. Once enabled, you
  cannot serve HTTP for `max-age` seconds — get this right before
  flipping the switch.

### Auth

- `PAIN001_API_KEY` is a single bearer token. Rotate every 90 days
  (the API has no built-in rotation; rotate by deploying a new
  token + the old in `PAIN001_API_KEY_FALLBACK`, then dropping the
  fallback after migration).
- For per-customer auth, terminate at a gateway (Cloudflare, Kong,
  Tyk) that adds the Pain001 bearer post-auth.

### Secrets

- Never bake secrets into the image. The compose `env_file`
  pattern is fine; for K8s, use `Secret` resources.
- The `data/redis` AOF can include the contents of API requests
  (job payloads). Treat that directory as sensitive — `chmod 0600`,
  encrypt at rest, never check into git.

### Network

- Expose only nginx's 443 (and 80 for the redirect). Everything
  else stays on the docker network.
- Block egress from the pain001 container except to:
  - Redis (loopback / cluster IP)
  - Your bank's API / SFTP endpoint (when v0.0.56 `pain001 upload`
    ships)
  - Optional: OpenTelemetry collector endpoint

### Logging

- Redact request bodies before shipping to a log aggregator (Pain001
  redacts IBAN / BIC / name from its own structured logs; nginx
  access logs are NOT redacted by default).
- Retention: regulatory requirement varies. EU SEPA: 7 years for
  the payment file itself; logs typically 90-day rolling.

### Vulnerability scanning

- Pin to a specific image digest (`pain001@sha256:...`), not just
  `:0.0.53`. The sha256 is in every release's GitHub Release page.
- Run `trivy image ghcr.io/sebastienrousseau/pain001:0.0.53` weekly.
- Subscribe to GitHub security advisories on
  `sebastienrousseau/pain001` (one-click in the repo's
  Security tab).

---

## Cost notes

For a workload of 50,000 payments / day generating ~5 GB of XML:

| Item | Spec | Indicative cost (USD/mo, mid-2026) |
| :--- | :--- | ---: |
| Compute (1 host) | 4 vCPU, 8 GB RAM | $40-80 |
| Storage (volumes) | 50 GB SSD | $5 |
| Bandwidth (egress) | 100 GB/mo | $10 |
| TLS cert | Let's Encrypt | $0 |
| Backup (S3 + lifecycle) | ~150 GB | $5 |
| **Total** | | **$60-100/mo** |

HA setup (2 hosts + managed Redis): ~$300-500/mo.
Multi-region active/active: $2-5k/mo, dominated by bandwidth.

If pain001 is generating files worth millions of dollars, this is
not the line item to optimise.

---

## When *not* to follow this cookbook

- **You only need the CLI.** Don't deploy the REST API. `pip
  install pain001`, run from cron or your CI/CD, done.
- **You're already on Kubernetes.** This compose stack is a useful
  reference for the env vars + topology, but use the matching Helm
  chart instead (community-maintained, see
  [`pain001-helm`](https://github.com/sebastienrousseau/pain001#companion-packages)
  status in the README; if it's not listed, the chart isn't ready
  yet and this compose file is the best reference until it is).
- **You're processing payments at FAANG scale.** > 10k req/s,
  multi-region, multi-bank-corridor: this is a different conversation;
  see [SUPPORT.md](../SUPPORT.md#support-tiers).

---

## Feedback

Found a sharp edge in this cookbook? Open a PR or an issue.
Production-deployment friction is the most valuable feedback we
can get — far more than feature requests.

See also:

- [OPERATIONS.md](../OPERATIONS.md) — the reference (every env var,
  every metric, every endpoint)
- [SECURITY.md](../SECURITY.md) — threat model + reporting
- [docs/quickstart.md](quickstart.md) — for users who haven't
  deployed pain001 anywhere yet
