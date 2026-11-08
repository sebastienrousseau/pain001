<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0009. Refuse an unauthenticated non-loopback bind in `pain001 serve`

- **Status:** Accepted
- **Date:** 2026-11-08
- **Deciders:** Sebastien Rousseau (maintainer decision D9)

## Context

The REST API authenticates only when `PAIN001_API_KEY` is set; unset,
every endpoint (generation, download, the dashboard) is open, which is
what makes local runs need no setup. Until 0.0.80, `pain001 serve
--host 0.0.0.0` started that open server on every interface without a
word, and the Dockerfile, `OPERATIONS.md` and the deployment cookbook
all showed that command. One forgotten environment variable exposed a
payment-file generator to the network.

## Options considered

1. Keep the open default and document the risk. No break for anyone,
   but the unsafe configuration stays one flag away and silent.
2. Require a key for every bind, loopback included. Safest, but breaks
   the zero-setup local run the CLI and examples rely on.
3. Allow loopback without a key; refuse any other address without one
   unless the operator opts in explicitly (`--insecure` or
   `PAIN001_ALLOW_INSECURE=1`). Local runs are unchanged, an exposed
   server needs a key or a deliberate, visible opt-out.

## Decision

Option 3. `pain001 serve` checks the host before starting uvicorn:
`127.0.0.0/8`, `::1` and `localhost` are allowed without a key; any
other host, wildcards and names included, is a usage error (exit 2)
that names both ways out. An opt-in prints a warning. Loopback stays
open because that is where the local-development promise lives, and
an opt-out keeps trusted-network experiments possible without a key.

## Consequences

- Breaking for anyone who ran `serve --host 0.0.0.0` (or another
  public address) without `PAIN001_API_KEY`: they must set the key or
  add `--insecure`.
- `uvicorn pain001.api.app:app` started directly bypasses the check,
  because an ASGI application does not see the address its server is
  bound to. The app logs a start-up warning when no key is set instead.
- `tests/test_cli_serve.py` pins every branch: refused hosts, loopback
  forms, the key, the flag and the environment variable.
