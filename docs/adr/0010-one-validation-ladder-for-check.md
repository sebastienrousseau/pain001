<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0010. One validation ladder behind every check surface

- **Status:** Accepted
- **Date:** 2026-11-08
- **Deciders:** Sebastien Rousseau (implementation plan, release 0.0.82)

## Context

Until 0.0.82 pain001 validated only what it was writing: rows before
rendering, then the rendered XML against its XSD, and a Schematron
rulebook or scheme profile when asked. A file that already existed (one
a bank returned, another tool wrote, or an older release produced) had
no check, although the corpus build already ran a full ladder on every
file it built (ADR-0003: XSD, MDR cross-element rules, scheme profiles
on the row projection, overlays). 0.0.82 adds the missing check on four
surfaces at once: the CLI, REST, the MCP server, and CI (a GitHub Action
and pre-commit hooks).

## Options considered

1. Each surface validates on its own, reusing whichever helpers fit.
   Fastest to write, but the surfaces would drift: a rung added to the
   CLI would be missing from REST, and a finding phrased one way in the
   terminal would read another way in SARIF.
2. Shell out to the CLI from REST, MCP and the Action. One code path,
   but every call pays a process start-up, results have to be parsed
   back from text, and a server would run subprocesses per request.
3. One library function, `pain001.check.check_document`, returning one
   report type; every surface calls it and only renders the report.

## Decision

Option 3. `check_document(xml, scheme=, policy=, schematron=)` reads
the message type from the document's namespace, runs the rungs in a
fixed order (`xsd`, `mdr`, then `scheme` and `schematron` when asked)
and returns a `CheckReport` of `CheckFinding`s (rung, rule, severity,
message, location). Every rung runs even when an earlier one fails, so
a caller sees every problem in one pass. The surfaces only translate:

- `pain001 check` renders text, JSON or one SARIF 2.1.0 log, and maps
  the report to exit 0 (passed), 1 (an error finding) or 2 (the file
  cannot be checked);
- `POST /api/v1/check` returns the report as JSON on the bounded
  pipeline pool, `422` when the document cannot be checked, and accepts
  Schematron presets only, never a server path;
- the MCP server's tool calls the same function on inline text;
- the GitHub Action and the pre-commit hooks run the CLI.

Refusals are typed: `NotAPaymentDocument` (well-formed XML of another
kind, which `--skip-other-xml` may skip) is a `ValueError`, like every
other reason a document cannot be checked (malformed XML, a DTD, a
version pain001 does not bundle, more than 10 MiB).

## Consequences

- A new rung is added once, in `pain001.check`, and every surface gets
  it; the rung names and finding shape are a contract for SARIF rule
  ids (`<rung>/<rule>`) and for JSON consumers.
- The overlays rung of the corpus ladder is not part of `check` yet: it
  needs a scenario to select overlays, which an arbitrary file does not
  have.
- Building it surfaced two defects that are fixed in the same release:
  the bundled Schematron rulebooks matched nothing on pain.001.001.04 to
  .13 and passed them silently (a rulebook that runs no rule is now a
  warning finding), and the .09 to .13 samples failed SEPA themselves.
- `tests/test_check.py`, `tests/test_cli_check.py`,
  `tests/test_api_check.py` and `tests/test_ci_surfaces.py` pin the
  engine and each surface.
