<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Verify a release

Every pain001 release is built by the tag workflow in
[`.github/workflows/ci.yml`](https://github.com/sebastienrousseau/pain001/blob/main/.github/workflows/ci.yml)
(jobs `build`, `publish`, `provenance` and `release-notes`) from a signed tag.
These steps check that what you install came from that workflow and was
not changed afterwards. Replace `0.0.85` with the version you are
checking.

## What a release attaches

| Asset | What it is |
| :--- | :--- |
| `pain001-<version>-py3-none-any.whl`, `pain001-<version>.tar.gz` | The wheel and source distribution published to PyPI |
| `pain001-<version>.cdx.json`, `pain001-<version>.cdx.xml` | CycloneDX SBOM of the runtime dependency tree |
| `pain001-<version>.spdx-licenses.json` | Licence report for every runtime dependency |
| `pain001-<version>.facts.json` | Version, extras and counts the website and MCP manifests render from |
| `SHA256SUMS` | SHA-256 of the six files above |
| `multiple.intoto.jsonl` | SLSA Build Level 3 provenance whose subjects are the same six files, signed with Sigstore |
| `pain001-<version>-evidence-pack.zip` | These assets plus the review documents, from 0.0.85 |

## 1. The tag

Tags and commits are signed with SSH keys listed in
[`KEYS.asc`](https://github.com/sebastienrousseau/pain001/blob/main/KEYS.asc)
(OpenSSH allowed-signers format; its history is the trust log).

```bash
git clone https://github.com/sebastienrousseau/pain001
cd pain001
git config gpg.ssh.allowedSignersFile KEYS.asc
git verify-tag v0.0.85
```

## 2. The checksums

```bash
gh release download v0.0.85 --repo sebastienrousseau/pain001 --dir release
cd release
sha256sum --check --ignore-missing SHA256SUMS
```

To check the package pip would install, download it from PyPI and
compare it with the same file:

```bash
pip download pain001==0.0.85 --no-deps -d pypi/
sha256sum pypi/*
```

## 3. The GitHub build attestation

The `publish` job attests the wheel and the sdist that the `build` job
produced, after checking them against the build job's hashes, with
`actions/attest-build-provenance`, bound to this repository's workflow
identity:

```bash
gh attestation verify pain001-0.0.85-py3-none-any.whl --owner sebastienrousseau
gh attestation verify pain001-0.0.85.tar.gz --owner sebastienrousseau
```

## 4. The SLSA provenance

The `provenance` job runs the SLSA GitHub generator, which signs
provenance for the six files in `SHA256SUMS` through Sigstore:

```bash
# slsa-verifier: https://github.com/slsa-framework/slsa-verifier
slsa-verifier verify-artifact pain001-0.0.85-py3-none-any.whl \
  --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/sebastienrousseau/pain001 \
  --source-tag v0.0.85
```

Repeat for the sdist, the SBOMs, the licence report and the facts file.

## 5. The PyPI upload

The package is published with PyPI trusted publishing (OpenID Connect
from the release workflow, no long-lived token) and with PEP 740
attestations (`attestations: true` in the publish step). PyPI shows
them on each file's page.

## 6. The evidence pack

The pack's `MANIFEST.json` lists the SHA-256 of every file in it. The
release assets it contains are the same bytes as the release's own
assets, so `sha256sum --check --ignore-missing SHA256SUMS` passes inside
the unpacked `release-assets/` folder too. The pack itself is created
after the provenance, so it is not one of the provenance subjects; its
checksum is listed in the release notes.
