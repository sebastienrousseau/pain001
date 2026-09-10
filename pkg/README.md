<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# pkg/

Distribution channels for `pain001`, one entry per format. The family
standard reserves this directory for generated packaging (deb, rpm,
AUR, Homebrew, Nix); the table says what exists today so nobody reads a
promise into an empty folder.

| Format | Status | Where |
| :--- | :--- | :--- |
| PyPI wheel and sdist | Shipped on every tag, trusted publishing, SLSA provenance, SBOM | `ci.yml` |
| Container image (GHCR, linux/amd64 + arm64, attested) | Shipped on every tag and on `main` | `docker.yml`, `Dockerfile` |
| deb, rpm | Not maintained | see [docs/packaging.md](../docs/packaging.md) |
| Homebrew, AUR, Nix | Not maintained | see [docs/packaging.md](../docs/packaging.md) |
| Single-file binaries | Not applicable: the CLI is a Python entry point | — |

- [VERIFY.md](VERIFY.md): how to verify a tag, a wheel, an SBOM, the
  container image and a commit.
- [docs/packaging.md](../docs/packaging.md): notes for distribution
  maintainers (licence grant, toolchain floor, pin model, offline tests).
