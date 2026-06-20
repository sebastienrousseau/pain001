<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Awesome-list submission cheatsheet

Pre-drafted entries + `gh` commands to submit the pain001 suite to
the major curated lists. Run these from outside the pain001 repo
(each submission forks the target list to your account, edits the
README, and opens a PR upstream).

Aim for the top three first; the long tail is in
[Optional submissions](#optional-submissions).

---

## 1. awesome-mcp-servers (highest leverage)

The pain001-mcp server has 16 tools spanning generation, validation,
parsing, migration, and ISO 20022 charset sanitisation — a genuine
fit.

**Target:** <https://github.com/punkpeye/awesome-mcp-servers>
**Section:** "Finance & Fintech" (or "Other" if not present)

### Suggested entry

```markdown
- [pain001-mcp](https://github.com/sebastienrousseau/pain001-mcp) — 16 MCP tools for generating and validating ISO 20022 pain.001 / pain.008 / camt.053 / pain.002 payment messages. Includes IBAN/BIC validation, cross-version pain.001 migration, in-memory XSD validation, and ISO 20022 Latin charset sanitisation. Python (FastMCP), Apache-2.0.
```

### Submit it

```bash
cd /tmp && rm -rf awesome-mcp-servers
gh repo fork punkpeye/awesome-mcp-servers --clone --remote
cd awesome-mcp-servers
git checkout -b add-pain001-mcp

# Manually edit README.md - find the Finance/Fintech section and
# insert the entry alphabetically. The list is alphabetical within
# section; pain001-mcp lives between "p" entries.
$EDITOR README.md

git add README.md
git commit -S -m "Add pain001-mcp (ISO 20022 payment messages)"
git push origin add-pain001-mcp
gh pr create --title "Add pain001-mcp (ISO 20022 payment messages)" \
  --body "$(cat <<'EOF'
Adds [`pain001-mcp`](https://github.com/sebastienrousseau/pain001-mcp), an MCP server exposing the [`pain001`](https://github.com/sebastienrousseau/pain001) ISO 20022 payment library as 16 first-class agent tools.

**Why include:** ISO 20022 is the global payments messaging standard (every SEPA, FedNow, and CBPR+ payment rides on it); there's no MCP server for it on this list today. The package is Apache-2.0, has 100% line + branch coverage, ships sigstore-attested wheels, and follows the alphabetical convention of nearby entries.

**Tool surface:** schema discovery, validation (records + IBAN/BIC + XML against XSD), generation (sync + async + from CSV), bank-reply parsing (camt.053 + pain.002), cross-version pain.001 migration, ISO 20022 charset sanitisation.

Verified the entry style + alphabetical ordering against the existing Finance section.
EOF
)"
```

---

## 2. awesome-language-servers

**Target:** <https://github.com/lazureykis/awesome-language-servers>

### Suggested entry

```markdown
- [pain001-lsp](https://github.com/sebastienrousseau/pain001-lsp) — LSP server for ISO 20022 pain.001 payment-data JSON files: diagnostics (JSON Schema + IBAN/BIC), completion, hover, "add missing required fields" code action, formatting, and a document-symbol outline. Python (pygls), Apache-2.0.
```

### Submit it

```bash
cd /tmp && rm -rf awesome-language-servers
gh repo fork lazureykis/awesome-language-servers --clone --remote
cd awesome-language-servers
git checkout -b add-pain001-lsp
$EDITOR README.md
git add README.md
git commit -S -m "Add pain001-lsp (ISO 20022 payment-data JSON)"
git push origin add-pain001-lsp
gh pr create --title "Add pain001-lsp (ISO 20022 payment-data JSON)" \
  --body "Adds [\`pain001-lsp\`](https://github.com/sebastienrousseau/pain001-lsp), a pygls Language Server for the JSON record format consumed by the pain001 ISO 20022 payment library. Six features (diagnostics, completion, hover, code actions, formatting, document symbols), 100% test coverage, Apache-2.0, runs against VS Code / Neovim / Helix / Emacs / any LSP client."
```

---

## 3. awesome-fintech / awesome-finance

The choice depends on which list is most-starred + most-actively-
maintained at submission time. Common targets:

- <https://github.com/sundowndev/awesome-fintech>
- <https://github.com/Cgboal/awesome-finance>
- <https://github.com/ATFutures/awesome-financial-data>

### Suggested entry (for `pain001` itself, not just the MCP/LSP)

```markdown
- [pain001](https://github.com/sebastienrousseau/pain001) — ISO 20022 payment-file (pain.001 / pain.008) generator with mandatory XSD validation, scheme rulebooks (SEPA SCT/SDD/INST/B2B + cross-border), every input format (CSV, SQLite, JSON, JSONL, Parquet, Excel via plugin), and CLI + REST + MCP + LSP surfaces. Python 3.10+, Apache-2.0, 100% test coverage.
```

---

## Optional submissions

### awesome-iso20022 *(may not exist as a curated list yet)*

If <https://github.com/topics/iso-20022> hasn't grown a curated list,
consider **creating** one (the topic itself has > 80 repos as of mid-
2026 but no awesome list). The four pain001-suite repos would be a
natural seeding.

### awesome-python

**Target:** <https://github.com/vinta/awesome-python>
**Section:** "Financial" (already exists)

The list has strict acceptance criteria. Requirements pain001 meets:
1k+ stars (check at submission time), active maintenance, clear
README, license, tests. Submit only if pain001 has cleared the 1k
star threshold — otherwise the PR is auto-closed by the bot.

### Hacker News Show HN

Not an awesome list, but the highest-leverage single discoverability
event you can run. Best post on a **Tuesday at 9am UTC** (peak EU +
US East Coast overlap). Title format:

> Show HN: Pain001 v0.0.53 — a 100%-test-coverage ISO 20022 payment library suite

Lead with the SEPA B2B profile + the in-memory XSD validation tool;
those are the genuinely-new bits worth opening with.

---

## Submission tracker

| Target | Submitted? | PR URL | Merged? |
| :--- | :--- | :--- | :--- |
| awesome-mcp-servers | _no_ | | |
| awesome-language-servers | _no_ | | |
| awesome-fintech | _no_ | | |
| awesome-iso20022 (TBD) | _no_ | | |
| Hacker News Show HN | _no_ | | |

Update this row when each lands.
