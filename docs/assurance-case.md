# Assurance case

An assurance case is an argument, backed by evidence, that a system's
security requirements are met. This one covers Pain001: what it is
trusted to do, where its trust boundaries lie, which design principles
were applied, and how the implementation weaknesses that matter for a
tool of this shape are countered.

It is written to be falsifiable. Every claim below points at code, a CI
gate, or a published artefact, so a reader can check it rather than take
it on faith. Where a control is absent, that is stated rather than
softened.

Scope: the `pain001` Python package, its CLI, its optional REST API
(`pain001 serve`, the `api` extra), and the published container image.
The companion packages (`pain001-mcp`, `pain001-lsp`, the loaders) ship
separately and carry their own policies.

---

## 1. What the software does, and what it is trusted for

Pain001 converts payment data a treasury team already holds
(spreadsheets, ERP exports, legacy SWIFT MT101 files) into ISO 20022
payment-initiation XML, and validates that XML against the official ISO
schemas before it is sent to a bank.

The security-relevant properties a user depends on are:

1. **Confidentiality of payment data.** Files contain IBANs, account
   names, and amounts. The tool must not transmit them anywhere.
2. **Integrity of generated output.** A generated `pain.001` must
   faithfully represent the input. A silently corrupted amount or
   creditor account is the worst realistic failure.
3. **Truthfulness of validation results.** "Valid" must mean the file
   passed the real ISO schema, not a permissive stand-in.
4. **Integrity of the distribution.** What a user installs must be what
   was built from this source.

Property 3 is called out explicitly because it has failed before: two
shipped schemas were hand-authored placeholders permissive enough to
accept documents ISO does not allow, which masked a defect that would
have caused every generated `pain.008` file to be rejected by a bank.
That is the failure mode this document exists to keep honest.

---

## 2. Threat model

`SECURITY.md` states what the library deliberately is **not** — not an
HSM, not a transport, not a settlement engine. This section states what
it must withstand.

**In scope**

| Threat | Concern |
|---|---|
| Malicious or malformed input file | A crafted CSV/XLSX/XML causing code execution, XXE, entity expansion, or resource exhaustion |
| Malicious template | A crafted Jinja template escaping into arbitrary execution (countered by `SandboxedEnvironment`, §5) |
| Hostile dependency | A compromised or typosquatted package entering the build |
| Tampered distribution | A modified wheel, sdist or image reaching a user |
| Untrusted plugin | A third-party loader executing in a locked-down environment |
| Exposed REST API | The optional API reached by an unauthenticated party |
| Data exfiltration | Payment data leaving the host by any path |

**Out of scope**, with reasons

- **A compromised host.** If the machine running Pain001 is controlled
  by an attacker, payment data on it is already lost. No user-space
  tool can restore that.
- **Bank-side acceptance.** Schema validity is not settlement. The tool
  states this on every result surface; it is a correctness boundary,
  not a security one.
- **Key management.** Pain001 holds no signing keys and performs no
  payment authorisation. Channel credentials belong to the bank's
  EBICS/SFTP/API client.

---

## 3. Trust boundaries

```
  ┌─ untrusted ─────────────────────────────────────────┐
  │  input files (CSV, XLSX, MT101, JSON, XML)          │
  │  ISO schemas and templates supplied via --schema    │
  │  third-party plugins discovered via entry points    │
  │  REST API requests                                  │
  └──────────────────────┬──────────────────────────────┘
                         │  ← boundary 1: parsing and validation
  ┌─ trusted ────────────┴──────────────────────────────┐
  │  pain001 core: mapping, generation, XSD validation  │
  │  bundled ISO schemas and templates                  │
  └──────────────────────┬──────────────────────────────┘
                         │  ← boundary 2: process and filesystem
  ┌─ operator's environment ────────────────────────────┐
  │  output directory, logs, metrics                    │
  └─────────────────────────────────────────────────────┘
```

**Boundary 1 — everything crossing it is untrusted.** Input files are
parsed by hardened parsers, never `eval`-ed or executed. XML parsing
uses `defusedxml`, so external entities and entity-expansion attacks are
refused rather than mitigated after the fact. The project deliberately
does not depend on `lxml`.

**Boundary 2 — the process writes only where instructed.** `-o` is an
output *directory*; the tool creates files there and nowhere else. It
opens no outbound network connections: there is no `requests`, `httpx`,
`urllib` or socket use anywhere in the package, which is what makes the
"nothing leaves your machine" claim checkable rather than promised.

**Plugins sit outside the trust boundary by default.**
`PAIN001_DISABLE_PLUGINS=1` disables discovery entirely, and
`pain001 plugins list` / `pain001 plugins show <name>` make every
discovered plugin auditable before first use — the control that matters
in a bank's locked-down environment.

---

## 4. Secure design principles applied

**Least privilege.** No network egress. No credential storage. No
elevated permissions. The container runs as a non-root user. CI tokens
are scoped `contents: read` by default, with write permissions granted
per job only where a job publishes.

**Fail closed.** Validation is a gate, not a warning: the demo and the
CLI refuse to emit XML when validation fails rather than emitting it
with a caveat. A `pain.002` response in a version whose schema is not
bundled is refused explicitly instead of being silently skipped.

**Economy of mechanism.** The XML path uses `xmlschema` and `defusedxml`
only. Declining `lxml` removes a large C surface from a tool whose whole
job is parsing hostile input.

**Complete mediation.** Every generated document is validated against
the bundled ISO schema on the way out, not only on request.

**Defence in depth for the optional API.** Bearer-token auth gated on
`PAIN001_API_KEY`, configurable rate limiting with an optional
Redis-backed distributed backend, and a versioned `/api/v1` surface. The
documented deployment assumption is a reverse proxy terminating TLS and
handling authentication; the API is not intended to face the internet
directly, and `docs/deployment-cookbook.md` says so.

**Open design.** The security of the tool does not depend on any part of
it being secret. Sources, schemas, CI configuration and release
provenance are all public.

---

## 5. Common implementation weaknesses, and how they are countered

| Weakness | Countermeasure | Evidence |
|---|---|---|
| XXE / entity expansion (CWE-611, CWE-776) | `defusedxml` for all XML parsing; no `lxml` | `pain001/xml/`, dependency set |
| Injection into generated XML (CWE-91) | Jinja `SandboxedEnvironment` with `select_autoescape`; values are data, never markup | `pain001/xml/generate_xml.py:394` |
| Path traversal (CWE-22) | Output is a directory the operator names; no filename is taken from input data | CLI `-o` handling |
| Deserialisation of untrusted data (CWE-502) | No `pickle`, `yaml.load`, or `eval` on input | `tests/`, CodeQL |
| Uncontrolled resource consumption (CWE-400) | Streaming mode with `--chunk-size`; API rate limiting | `--streaming`, `PAIN001_RATE_LIMIT` |
| Dependency confusion / compromise (CWE-1357) | Hash-pinned requirements for every CI job and the container image; Dependabot; `pip-audit` and Snyk on every commit | `requirements.txt`, `.github/requirements/*.txt` |
| Tampered distribution (CWE-494) | Sigstore-signed SLSA Build L3 provenance covering every release artefact, verifiable with `slsa-verifier`; signed git tags | `multiple.intoto.jsonl` on each release |
| Silent validation failure | Every bundled schema must exceed 10 KB, define ≥5 complex types, and *behaviourally reject* a junk document | `tests/test_schema_completeness.py` |
| Untested code paths | 100% branch coverage enforced as a CI gate (`--cov-fail-under=100`) | `pyproject.toml`, CI |
| Unknown parser crashes | Atheris fuzzing harness over the validation path | `fuzz/fuzz_validation.py` |
| Static defects | CodeQL on every push; ruff lint enforced in CI | `.github/workflows/codeql.yml` |

The schema-completeness test deserves emphasis: it is the direct
response to the placeholder-schema incident in §1. Structural checks
alone would have passed the permissive schema — the behavioural
"must reject junk" assertion is what makes the gate meaningful.

---

## 6. Known limitations

Stated because an assurance case that claims everything is complete is
not credible.

- **Single maintainer.** Changes are self-merged after CI. Branch
  protection requires a pull request and passing checks for everyone
  including administrators, but a second reviewer does not exist. This
  is the project's largest residual risk and it cannot be closed by
  configuration.
- **No independent security review** has been commissioned.
- **TLS is out of scope for the API.** It expects a reverse proxy.
  Running `pain001 serve` directly on a public interface is not a
  supported deployment.
- **Bank acceptance is not assured.** Four layers govern whether a file
  is accepted — ISO schema, scheme rulebook, bank profile, and channel
  eligibility — and Pain001 checks the first two.

---

## 7. How to check these claims

```bash
# No outbound network calls anywhere in the package
grep -rE '\b(urlopen|requests\.|httpx\.|aiohttp)' pain001/   # expect: no matches

# Release provenance covers every artefact and binds to the tag
slsa-verifier verify-artifact pain001-<version>-py3-none-any.whl \
  --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/sebastienrousseau/pain001 \
  --source-tag v<version>

# Coverage gate and schema honesty gate
make test          # fails below 100% branch coverage
poetry run pytest tests/test_schema_completeness.py
```

Reports of anything here being untrue are handled under `SECURITY.md`,
which commits to acknowledgement within 48 hours and a triage plan
within 7 days.
