<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Verify the published ecosystem

The family inventory is [ecosystem.json](ecosystem.json). It names all nine
repositories, their release titles and their actual publication channels.
The README and roadmap component tables are generated from this inventory.
`pain001/suite.py` remains the policy table for the five PyPI distributions;
it is not the complete publication inventory.

Run `make ecosystem-check` to audit the latest published core and require
every member's latest publication to match. Python 3.11 or later and `curl`
are required. No additional Python packages are needed. `GH_TOKEN` or
`GITHUB_TOKEN` supplies read-only GitHub API access; public requests also
work without a token, subject to GitHub's lower anonymous rate limit.

Use `make ecosystem-check VERSION=0.0.82` to select an explicit version.
This selects its GitHub tags and PyPI metadata, but still checks the live
containers and website. It does not reconstruct a historical deployment.
For machine output, use `python3 scripts/check_ecosystem.py --json`; add
`--output report.json` to retain the evidence even when the audit fails.

## What is checked

- Every active pain001 repository discovered on GitHub appears in the
  inventory. A new or missing repository fails rather than being skipped.
- All nine GitHub releases have the expected stable version and project
  title, a signed annotated tag verified by GitHub, and a commit target.
  Notes follow the global Highlights, changes, checksums and changelog
  format. Every attached asset is listed exactly once and its checksum
  agrees with GitHub's asset digest.
- All five PyPI distributions have non-yanked wheel and source artifacts
  whose hashes match their GitHub assets. Companion core dependency floors
  equal the suite version.
- The core, MCP, LSP and mockbank versioned GHCR images contain Linux amd64 and
  arm64 manifests. Content-addressed manifests and configs are hash-checked;
  each image's version and revision labels match the signed release tag.
- The deployed website runtime identifies the suite version and pins the
  exact core wheel hash published on PyPI.
- The MCP Registry has an active server record whose version, repository
  and PyPI package agree with the suite. The latest audit also requires
  that record to be the registry's latest version.
- Required GitHub-only payloads remain present, including all five native
  wheels, the scaffold source archive, the website archive and SBOM, the
  mockbank image reference, and the LSP VSIX. Marketplace publication is
  optional in the LSP workflow; the downloadable VSIX is required.

The scheduled audit compares GitHub's asset digests; it does not download
every release binary. Full artifact downloads and cryptographic build/image
attestation verification remain part of the release's post-publication
checklist. A signed tag does not establish artifact provenance on its own.

## CI and partial rollouts

The core's Suite Consistency workflow runs daily and on dispatch, from
trusted default-branch code with a read-only token. It does not run on
another workflow's completion (`workflow_run`): the core publishes
first, so an audit straight after its release can only report the
companions that have not shipped yet, and each companion runs the audit
after its own publication. Dispatch the core's workflow once the last
member is out. A standalone `release: published` trigger would not help
either, because releases created with `GITHUB_TOKEN` do not launch
another workflow; see GitHub's
[workflow triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

The shared `.github/actions/check-ecosystem` action lets companions run the
same checker pinned to a reviewed core commit. They watch their own release
workflow completion. No cross-repository dispatch credential is required.
`scripts/render_ecosystem_workflows.py --core-ref COMMIT --out DIRECTORY`
generates all eight companion workflow updates for review. Publishing
workflow names come from the inventory; the website also rechecks after its
main-branch CI completes the Pages deployment.

A core release may finish before its companions. During that rollout the
audit must fail and name the missing members. A version bump, merged PR or
successful core publish is not a complete family release. Each subsequent
publication runs the audit again; the final member's audit should succeed.
Network failures, missing metadata, rate limits and stale deployment caches
produce failed reports too. Do not add exceptions or skip a member to turn
a partial rollout green.

The workflow retains `ecosystem-publication.json` on success and failure.
Offline tests use synthetic transport responses, with separate 100% line
and branch coverage enforced by `make test-publications`. The package's
existing 100% coverage gate remains unchanged.

## Updating the inventory

Edit `docs/ecosystem.json` after a maintainer decides that a member joins
the family or changes publication channels. Update the inventory contract
test, regenerate both component tables with `scripts/render_readme.py` and
`scripts/render_ecosystem_docs.py`, and run the local gates. Never infer that
a GitHub-only member should also be published to PyPI or crates.io.
