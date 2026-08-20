<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Plugin architecture

> *Stability:* the contract documented here is stable within a major
> version. The current contract version is `(0, 54)`; see
> [Versioning](#versioning) for the upgrade policy.

`pain001` v0.0.54 ships a formal plugin substrate so external packages
can extend it without forking. Four kinds of plugins are supported:

| Kind | Protocol | Use it when you want to … |
| :--- | :--- | :--- |
| Loader | `AbstractLoader` | Read a new file format (`.xlsx`, `.csv.gpg`, `.proto`, …) into payment rows |
| Validator | `AbstractValidator` | Add an intra-record check (row-by-row; no batch context) |
| Scheme | `AbstractScheme` | Add a whole-batch rulebook (duplicate detection, batch totals, custom DSL) |
| Writer | `AbstractWriter` | Serialise rendered XML somewhere new (`sftp://`, `s3://`, …) |

Plugins are discovered at process start through
`importlib.metadata.entry_points` — no hooks to register manually, no
`pain001 plugin install` step. Drop a package in your environment and
`pain001 plugins list` shows it.

---

## Quick start: an Excel loader in 40 lines

```python
# In your package: my_pain001_xlsx/loader.py
from collections.abc import Iterable
from typing import Any

import openpyxl

from pain001.plugins import (
    PAIN001_API_VERSION,
    AbstractLoader,
    LoaderResult,
    PluginMeta,
)


class XlsxLoader:
    """Read pain001 payment rows from an Excel .xlsx file."""

    meta = PluginMeta(
        name="xlsx",
        version="0.1.0",
        description="Read flat-record payment data from Excel .xlsx files.",
        api_version=PAIN001_API_VERSION,
    )
    extensions = (".xlsx", ".xlsm")

    def load(self, path: str) -> LoaderResult:
        """Read every sheet-1 row into a list of dicts."""
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        rows = [
            dict(zip(headers, (c.value for c in row), strict=False))
            for row in ws.iter_rows(min_row=2)
        ]
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield rows in chunks of ``chunk_size``."""
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        buf: list[dict[str, Any]] = []
        for row in ws.iter_rows(min_row=2):
            buf.append(
                dict(zip(headers, (c.value for c in row), strict=False))
            )
            if len(buf) >= chunk_size:
                yield LoaderResult(rows=buf, source_hint=path)
                buf = []
        if buf:
            yield LoaderResult(rows=buf, source_hint=path)
```

Register the loader with pain001 via the standard
`importlib.metadata` entry-point mechanism in your
`pyproject.toml`:

```toml
[project.entry-points."pain001.loaders"]
xlsx = "my_pain001_xlsx.loader:XlsxLoader"
```

Install it next to pain001:

```bash
pip install my-pain001-xlsx pain001
pain001 plugins list
# loader  xlsx  my-pain001-xlsx==0.1.0  Read flat-record payment data from Excel .xlsx files.
pain001 -t pain.001.001.03 -d payments.xlsx
# generates pain.001.001.03.xml using your loader; nothing else changes.
```

That's the whole contract. No subclassing, no decorators, no global
state — pain001 picks the loader up by extension dispatch on first
use.

---

## The contract surface

### `AbstractLoader`

```python
class AbstractLoader(Protocol):
    meta: PluginMeta
    extensions: tuple[str, ...]  # (".xlsx", ".xlsm"), lower-case with dot

    def load(self, path: str) -> LoaderResult: ...
    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]: ...
```

- `extensions` is the **dispatch key**. The first installed loader to
  claim an extension wins on lookup; a later registration overrides
  earlier ones (the registry logs the override).
- `load_streaming` is required by `--streaming` mode. A loader that
  truly cannot stream may yield a single `LoaderResult` carrying every
  row.
- `LoaderResult.source_hint` is attached to downstream validation
  findings so users can locate the offending row.

### `AbstractValidator`

```python
class AbstractValidator(Protocol):
    meta: PluginMeta

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        message_type: str,
    ) -> ValidatorResult: ...
```

Use it for row-by-row checks: schema, types, identifier formats. Each
`ValidatorFinding` carries `row_index`, `field`, `rule`, `severity`,
`message` — all frozen dataclasses so they can be cached and hashed.

### `AbstractScheme`

```python
class AbstractScheme(Protocol):
    meta: PluginMeta

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        message_type: str,
    ) -> SchemeResult: ...
```

The whole-batch sibling. Use it for cross-record rules: duplicate
detection, batch totals, BIC reachability against a reference list,
the upcoming CEL custom-rule DSL. Findings carry an additional
`related_rows: tuple[int, ...]` so cross-record violations can point
at every contributing row.

### `AbstractWriter`

```python
class AbstractWriter(Protocol):
    meta: PluginMeta

    def write(self, xml: str, destination: str) -> str: ...
```

Takes the validated XML and a writer-specific destination string
(filesystem path, `sftp://user@host/path`, `s3://bucket/key`, …) and
returns a canonical sink identifier. Writers must not re-parse or
alter the XML — the generator owns canonical form.

---

## Discovery, registration, dispatch

```text
┌─────────────────────────────────────────────────────────┐
│         pain001 process start (lazy on first call)      │
├─────────────────────────────────────────────────────────┤
│  1. Built-in adapters register (csv, json, jsonl,       │
│     sqlite, parquet).                                   │
│  2. Entry-point groups are walked:                      │
│       pain001.loaders                                   │
│       pain001.validators                                │
│       pain001.schemes                                   │
│       pain001.writers                                   │
│  3. Each entry instantiates with no args; the registry  │
│     stamps `meta.source = "<dist>==<version>"`.         │
│  4. `PAIN001_DISABLE_PLUGINS` skips matching names.     │
└─────────────────────────────────────────────────────────┘
```

A broken plugin (one that raises at `load()` or instantiation) is
**skipped with a warning** — pain001 keeps running with the rest of
the registered plugins. The operator can find the culprit with
`pain001 plugins list` and the structured log line.

To disable a plugin without uninstalling it:

```bash
PAIN001_DISABLE_PLUGINS=parquet pain001 plugins list
PAIN001_DISABLE_PLUGINS="parquet, sqlite" pain001 generate ...
```

---

## CLI surface

```text
pain001 plugins list [--kind loader|validator|scheme|writer] [--json]
pain001 plugins show <name> [--kind ...]
pain001 plugins disable          # documentation-only; prints the env-var instructions
```

```bash
pain001 plugins list --json | jq '.[].name'
pain001 plugins show csv
# loader csv v0.0.54
#   source:      built-in
#   api version: 0.54
#   description: Read flat-record payment data from CSV files.
```

---

## Versioning

The plugin contract is **stable within a major version**. Today
that is `(0, 54)` and the major is `0`. Within `0.x`:

- **New methods** may be added to existing Protocols. Older plugins
  that don't implement them are *not* rejected — pain001 simply
  doesn't call the missing method on them.
- **New Protocols** may be added (new entry-point groups).
- **Existing methods** keep their signature; arguments are only added
  with defaults.

When a plugin declares `api_version = (M, N)` and the host pain001
is `(M, N')` with `N' < N`, the host logs a warning and loads the
plugin anyway (the plugin may rely on a method the host doesn't
expose; that method call would `AttributeError` if it tried). When
the plugin's *major* exceeds the host's, the host **refuses to
load it** with a `PluginVersionError` directing the operator to
upgrade pain001.

We will bump the major (and break the contract) only when there is
no compatible path forward — and the next major's first release will
provide a `pain001 plugins migrate <plugin>` helper.

---

## Built-in plugins

### Loaders

| Name | Extensions | Wraps |
| :--- | :--- | :--- |
| `csv` | `.csv` | `pain001.csv.load_csv_data` |
| `json` | `.json` | `pain001.json.load_json_data` |
| `jsonl` | `.jsonl` | `pain001.json.load_json_data` |
| `sqlite` | `.db`, `.sqlite` | `pain001.db.load_db_data` (reads from a `pain001` table) |
| `parquet` | `.parquet` | `pain001.parquet.load_parquet_data` (requires `pain001[parquet]`) |

A sixth, `gpg`, registers only when `pain001[gpg]` is installed; it
decrypts and delegates to whichever loader matches the inner extension
(`batch.csv.gpg` → `csv`).

### Schemes

| Name | Rulebook |
| :--- | :--- |
| `sepa-sct` | SEPA Credit Transfer (EUR, IBAN, charset limits) |
| `sepa-sdd` | SEPA Direct Debit (mandate id, sequence type) |
| `sepa-b2b` | SEPA B2B Direct Debit (B2B sequence types) |
| `sepa-inst` | SEPA Instant Credit Transfer (amount ceiling) |
| `xborder-ct` | Cross-border Credit Transfer (any ISO currency) |

These wrap the profiles in `pain001.validation.schemes`, which predate
the contract: they take `data` positionally and return
`SchemeValidationResult`. The adapter maps `index` → `row_index`,
attaches the remediation hint for the rule, and terminates the message,
because `SchemeFinding` requires a sentence and the legacy strings are
phrased without one.

`message_type` is accepted for contract conformance and is not used by
these five — a bundled profile is selected by name, not by message
type. An external scheme is free to branch on it.

### Writers

| Name | Destination |
| :--- | :--- |
| `xml-file` | A filesystem path. Creates missing parents; returns the resolved absolute path. |

The writer holds the XML bytes verbatim. Canonical form is the
generator's decision, so a writer that re-parsed or re-serialised could
silently change what a bank receives.

Everything above carries `meta.source = "built-in"`. They live in
`pain001/plugins/_builtins.py` and exercise the *same* contract any
external plugin uses, so a regression in the contract is caught
against the built-ins before it can hurt downstream packages.

Future ship under this contract (each tracked as its own roadmap
issue):

- `pain001-loader-xlsx` — Excel loader (v0.0.54)
- `pain001-loader-gpg` — composable GPG-decrypting wrapper (v0.0.54)
- `pain001-scheme-anti-duplicate` — cross-record duplicate detection
  (v0.0.55)
- `pain001-scheme-cel` — custom YAML rules over CEL (v0.0.55)

---

## Going further

- **Cookiecutter template:** `sebastienrousseau/pain001-plugin-template`
  scaffolds a plugin repo with CI, test harness, and the entry-point
  declaration pre-wired *(in progress)*.
- **Reference plugin:** any of the five built-in adapters in
  [`pain001/plugins/_builtins.py`](../pain001/plugins/_builtins.py).
- **Contract source:**
  [`pain001/plugins/contracts.py`](../pain001/plugins/contracts.py).
- **Registry source:**
  [`pain001/plugins/registry.py`](../pain001/plugins/registry.py).

Found a sharp edge? Open an issue tagged `plugin` — the contract is a
one-way door inside a major, so we'd rather hear about ergonomic
problems early.
