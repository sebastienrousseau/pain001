# syntax=docker/dockerfile:1.6
# Multi-stage build for a minimal pain001 image.
#
# The image ships the CLI (`pain001`) and, via the `api` extra, the
# FastAPI REST surface (`pain001 serve --host 0.0.0.0`). Multi-arch:
# linux/amd64 and linux/arm64.

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS builder

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pyproject.toml carries ``readme = "README.md"``, so README.md must be
# present at build-time for ``pip install .`` to resolve the package
# metadata.
COPY pyproject.toml README.md ./
COPY pain001 ./pain001
COPY requirements.txt ./
COPY .github/requirements/api.txt ./api-requirements.txt

# Self-contained virtualenv; install the package plus the `api`
# extra so `pain001 serve` works out of the box.
#
# Every third-party dependency comes from a hash-pinned file, then the
# package itself is installed with --no-deps. Previously this was a bare
# `pip install ".[api]"`, which resolved fastapi and uvicorn unpinned at
# image build time — the published image's web stack was whatever PyPI
# served that day.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes -r requirements.txt \
    && /opt/venv/bin/pip install --require-hashes -r api-requirements.txt \
    && /opt/venv/bin/pip install --no-deps ".[api]"


FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

LABEL org.opencontainers.image.title="pain001" \
      org.opencontainers.image.description="Generate and validate ISO 20022 payment files (pain.001 / pain.008) from CSV, SQLite, JSON, or Parquet." \
      org.opencontainers.image.source="https://github.com/sebastienrousseau/pain001" \
      org.opencontainers.image.url="https://pain001.com" \
      org.opencontainers.image.licenses="Apache-2.0"

# Non-root user.
RUN groupadd --system pain001 \
    && useradd --system --gid pain001 --home /home/pain001 pain001 \
    && mkdir -p /home/pain001 \
    && chown -R pain001:pain001 /home/pain001

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER pain001
WORKDIR /home/pain001

# A non-zero exit here means an import / dependency mismatch; the
# container orchestrator can pick it up before traffic arrives.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pain001" || exit 1

# Default to the CLI; ``docker run pain001 serve --host 0.0.0.0``
# brings up the REST API.
ENTRYPOINT ["pain001"]
CMD ["--help"]
