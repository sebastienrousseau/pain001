<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Verifying a pain001 release

Every release is built in GitHub Actions from a signed tag and ships
with material that lets you check it came from this repository and was
not altered afterwards.

## 1. The tag

```bash
git clone https://github.com/sebastienrousseau/pain001
cd pain001
git config gpg.ssh.allowedSignersFile KEYS.asc
git verify-tag v0.0.66
```

`KEYS.asc` is in allowed-signers format; its history is the trust log.

## 2. The PyPI package

`pain001` is published with PyPI trusted publishing (OIDC from the
release workflow, no long-lived token). Check the digest of what you
downloaded against the release assets:

```bash
pip download pain001==0.0.66 --no-deps -d dist/
sha256sum dist/*
```

Compare with the checksums attached to the GitHub release, then verify
the SLSA provenance that covers the wheel, the sdist and the SBOMs:

```bash
# slsa-verifier: https://github.com/slsa-framework/slsa-verifier
slsa-verifier verify-artifact dist/pain001-0.0.66-py3-none-any.whl \
  --provenance-path <the .intoto.jsonl asset from the release> \
  --source-uri github.com/sebastienrousseau/pain001 \
  --source-tag v0.0.66
```

## 3. The SBOM

Each release attaches a CycloneDX SBOM in JSON and XML plus an SPDX
licence report (`pain001-<version>.cdx.json`, `.cdx.xml`,
`.spdx-licenses.json`). They are covered by the same provenance as the
wheel from 0.0.59 onwards.

## 4. The container image

```bash
gh attestation verify oci://ghcr.io/sebastienrousseau/pain001:0.0.66 \
  --owner sebastienrousseau
```

The image is multi-arch (linux/amd64, linux/arm64) and its base image
is pinned by digest in the `Dockerfile`.

## 5. A commit

```bash
git verify-commit <sha>
```

Every commit also carries a `Signed-off-by` trailer (Developer
Certificate of Origin), enforced on pull requests.
