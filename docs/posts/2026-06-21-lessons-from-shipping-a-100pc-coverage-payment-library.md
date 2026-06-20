<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Lessons from shipping a 100%-coverage ISO 20022 payment library

*A solo-maintainer post-mortem on what worked, what didn't, and
what 100% line + branch coverage actually buys you when the
artefact moves real money.*

**Published:** 2026-06-21
**Author:** Sebastien Rousseau
**Project:** [`pain001`](https://github.com/sebastienrousseau/pain001) + 3-package suite

---

## TL;DR

I just shipped v0.0.53 of [`pain001`](https://github.com/sebastienrousseau/pain001),
a Python library that turns CSV / SQLite / JSON / Parquet payment
data into XSD-validated ISO 20022 XML the way your bank wants it.
The release closed every open issue and every open code-scanning
alert. It also moved the project to a **100% enforced coverage
floor** (line + branch + docstrings) — and along the way, three
companion packages (`pain001-mcp` for AI agents, `pain001-lsp` for
editors, `pain001-loader-xlsx` for Excel) shipped at the same
version under a coordinated release.

The headline metrics:

| | Before (v0.0.52) | **After (v0.0.53)** |
| :--- | ---: | ---: |
| Tests | 1,181 | **1,265** |
| Line + branch coverage | 99.85% (98% floor) | **100% (100% floor)** |
| Open CodeQL alerts | 1 high | **0** |
| Runnable examples in CI | 13 | **14** |
| Packages in the suite | 3 | **4** |

Below: what I learned, what I'd do differently, and what I think
the open-source community routinely gets wrong about "100% coverage."

---

## Why I built pain001

Three years ago I was integrating with a Single Euro Payments Area
(SEPA) bank's API. They wanted [pain.001.001.03](https://www.iso20022.org/iso-20022-message-definitions?business-domain=1)
XML. Their docs were 200 pages. Their sandbox rejected our first
12 attempts.

Each rejection cost a working day. The bug was always trivial in
hindsight — a misformatted `BIC`, a missing `<CtrlSum>` element, a
character outside ISO 20022's restricted Latin set. None of it
would have shipped if a local validator had said "this won't pass."

That validator didn't exist. There were two Python libraries; both
were abandoned, both rendered XML without schema validation.

So I wrote one.

## Why 100% coverage matters when the artefact is XML

Open-source coverage debates are usually theological. "100% is
cargo-culting." "Coverage measures the wrong thing." "You can have
100% coverage and zero useful tests." All true, in the median case.

But XML-generation code is unusual:

1. **The success criterion is binary.** A `pain.001` either
   validates against the XSD or it doesn't. There's no partial
   credit, no "works most of the time." If a code path can be
   reached and it produces invalid XML, that's a production bug
   waiting to happen.

2. **The failure mode is silent.** A misformatted file doesn't
   throw. It just gets rejected by the bank, hours later, by an
   automated system that emails a PDF rejection notice on Monday
   morning.

3. **The cost of a single shipped bug is the entire customer
   relationship.** A bank that gets garbage from your library
   stops trusting your library. You don't get a second chance to
   show them the corrected output; they're on the phone with their
   compliance team.

In this domain, "100% coverage" is the **cheapest** signal that
every code path has at least been seen by a human writing an
assertion. It's not sufficient — but it's necessary.

## What 100% coverage doesn't catch

About a dozen things, in my experience:

1. **Logic errors with the right shape.** If the test asserts
   `assert generate(rows) is not None`, you get 100% coverage of
   `generate()` and zero confidence the output is correct.

2. **Concurrency bugs.** Coverage tools don't measure thread
   interleaving. The Redis-backed rate limiter that ships in
   v0.0.53 has a real-world race condition that no unit test will
   catch; I caught it with `fakeredis` + a manually-stepped fake
   clock.

3. **Encoding issues.** Bytes-vs-str, CRLF-vs-LF, BOM handling.
   100% line coverage doesn't make ASCII vs UTF-8-with-BOM a
   visible failure.

4. **Integration drift.** Every XSD change from ISO 20022 is a
   potential silent break. Coverage tells you "the test ran"; it
   doesn't tell you "the test still matches reality."

5. **Performance regressions.** Coverage is binary (covered /
   uncovered). A code path can be covered and 100× slower than it
   was last release.

The discipline I've landed on: **100% coverage as a floor for
"have I seen this?", plus separate gates for "does it still do
the right thing?"** Concretely:

- `--cov-fail-under=100` for the line + branch question.
- `interrogate --fail-under=100` for "is every public surface
  documented?".
- Property-based tests (`hypothesis`) for invariants like
  "every generated CtrlSum matches the sum of input amounts."
- XSD validation against the official ISO 20022 schemas in every
  generator test.
- A separate `examples/` directory of self-checking scripts that
  CI runs end-to-end — these catch the "ran the code but didn't
  exercise the integration" failure mode.

## The pragma rule that kept me sane

Strict 100% coverage with no escape hatch leads to one of two bad
outcomes: either you contort the production code to make
unreachable defensive branches reachable, or you delete the
defensive branches that protect against the unreachable.

The third option: `# pragma: no cover` with a justification.

```python
plugin_loader = plugin_registry.get_loader_for_extension(ext)
if plugin_loader is None:  # pragma: no cover - guarded by early check
    # Belt-and-braces: the early extension check above already
    # confirmed a plugin claims this ext, so this is unreachable
    # unless the registry mutated between the two calls.
    raise DataSourceError(...)
```

The rule I enforce in code review: **every `# pragma: no cover`
must carry a one-line reason that survives a future reader
asking "why?".** No reason → reviewer rejects the PR. With the
rule, `# pragma: no cover` becomes a documentation tool, not a
coverage-cheat tool.

Out of ~3,000 lines of executable code, pain001 has 11 pragmas.
All eleven would survive that "why?" question.

## The plugin contract: the thing I'm proudest of

The other thing v0.0.54 introduces (currently on `feat/v0.0.54`,
not yet released) is a formal plugin contract. Four
[PEP 544 Protocols](https://peps.python.org/pep-0544/) —
`AbstractLoader`, `AbstractValidator`, `AbstractScheme`,
`AbstractWriter` — let external packages on PyPI extend pain001
without forking.

Why I'm proud of it: the canonical worked example,
[`pain001-loader-xlsx`](https://github.com/sebastienrousseau/pain001-loader-xlsx),
is ~150 lines. The integration with pain001 is one line in
`pyproject.toml`:

```toml
[project.entry-points."pain001.loaders"]
xlsx = "pain001_loader_xlsx.loader:XlsxLoader"
```

After `pip install pain001-loader-xlsx`, pain001 dispatches
`.xlsx` files to it automatically. No code change to pain001, no
central registry to update, no subclassing.

Why this matters: pain001 has one maintainer (me). The plugin
contract is the only realistic mechanism I have to let the
ecosystem outpace my bandwidth. A `pain001-loader-sap`, a
`pain001-scheme-ch`, a `pain001-mockbank-deutsche` — none of those
need to wait for me to merge.

The cribbed inspiration: [`pluggy`](https://pluggy.readthedocs.io/)
(pytest's plugin host), without pluggy's complexity. PEP 544
makes the "no forced inheritance" story trivial; entry points
solve discovery without a central registry.

If you're shipping a Python library that you want to outlive your
own bandwidth, **publish a plugin contract before you need it.**

## What I'd do differently

1. **Tag the plugin contract from day one.** I went three minor
   versions before formalising it. Every loader / scheme / writer
   shipped before v0.0.54 had to be migrated. If I'd published a
   `v0.0.x` API with Protocols from v0.0.1, the migration would
   have been free.

2. **Don't bundle CLI + library + REST + MCP + LSP in one repo.**
   Pain001 ships all five surfaces from one `pyproject.toml`. The
   MCP and LSP servers eventually moved to sibling packages (the
   v0.0.52 suite split). I should have started that way. Bundling
   was a 3-month optimisation for the wrong constraint.

3. **Stop saying "I'll get to marketing later."** I've shipped 53
   patch releases over 30 months. I've written zero blog posts
   before this one. The project's PyPI download numbers are roughly
   what you'd expect from "good engineering, zero distribution."
   Don't be me.

4. **Recruit a co-maintainer before you need one.** I've been
   inviting one in [`GOVERNANCE.md`](https://github.com/sebastienrousseau/pain001/blob/main/GOVERNANCE.md)
   for over a year. The first concrete recruitment DM I've sent
   was today. **Inviting is not recruiting.** The bus factor of
   one is the single biggest risk to this project and the slot is
   still open.

## What I got right

1. **"When not to use" sections in every README.** Pain001 doesn't
   transmit files, doesn't generate camt.052 / pacs.*, doesn't
   support EBICS, doesn't do fuzzy matching. Every README says so.
   Contributors stop opening PRs the project will reject;
   adopters stop expecting features that aren't coming. I should
   have started doing this five years ago for every project.

2. **Every example runs in CI.** The 14 examples in `examples/`
   are exercised by `tests/test_examples.py` on every commit. If a
   public API breaks the example, CI fails. The cost of writing
   them was a weekend; the value of "these scripts cannot rot" is
   permanent.

3. **The release pipeline is signed end-to-end.** Tags are signed
   with my SSH key. The PyPI Trusted Publisher uses OIDC, no
   long-lived tokens. The GHCR image is published with
   `docker/build-push-action`'s provenance attestations. v0.0.53
   added SBOMs (CycloneDX + SPDX) as Release assets. None of
   this was complicated; it just took deciding it mattered.

4. **The "no" list is public.** v0.0.53's `ROADMAP.md` has an
   explicit "Declined / deferred" table — EBICS, full SPA
   dashboard, fuzzy matching, cross-batch deduplication. Each one
   has a reason. People stop arguing about whether the project
   "should" do those things and start asking what the project
   *does* do.

## If you're shipping infrastructure code in 2026

Three things, in order:

1. **Publish a plugin contract.** Your bandwidth is your bottleneck.
   Decouple from it.
2. **Sign your releases.** Sigstore + OIDC trusted publishing on
   PyPI is ~3 hours of one-time work. After that, you stop having
   to think about it.
3. **Write the "no" list before you need it.** Future-you will
   thank past-you.

Things 2 and 3 are universal. Thing 1 only matters if you're
serious about the project outliving you.

## Try it

```bash
pip install pain001
pain001 init pain.001.001.03 -o payments.csv
# Edit payments.csv with your data
pain001 generate -t pain.001.001.03 -d payments.csv
# That's a validated ISO 20022 XML file, ready for your bank.
```

10-minute deep-dive: [`docs/quickstart.md`](https://github.com/sebastienrousseau/pain001/blob/main/docs/quickstart.md).
Production deployment: [`docs/deployment-cookbook.md`](https://github.com/sebastienrousseau/pain001/blob/main/docs/deployment-cookbook.md).
Full source + 14 runnable examples: [github.com/sebastienrousseau/pain001](https://github.com/sebastienrousseau/pain001).

If you use pain001 in production, [open a one-line issue](https://github.com/sebastienrousseau/pain001/issues/new?title=Production+user:+%5BYour+org%5D)
— it's the single highest-leverage thing you can give back.

If you're a Python maintainer interested in co-maintaining a
suite that moves real money, see
[`GOVERNANCE.md#becoming-a-maintainer`](https://github.com/sebastienrousseau/pain001/blob/main/GOVERNANCE.md).

---

*Comments / corrections welcome on the [companion Hacker News
thread](#) (link added once posted) or as a GitHub issue.*
