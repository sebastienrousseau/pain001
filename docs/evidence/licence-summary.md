<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Licence summary

## Pain001

Pain001 is licensed under **Apache-2.0 OR MIT**, at your option
(`license = "Apache-2.0 OR MIT"` in
[`pyproject.toml`](https://github.com/sebastienrousseau/pain001/blob/main/pyproject.toml);
texts in `LICENSE`, `LICENSE-APACHE` and `LICENSE-MIT`). Both licences
allow commercial use, modification and redistribution, with no fee and
no copyleft obligation. Every source file carries the SPDX header
`Apache-2.0 OR MIT`.

The licence also lets any firm support Pain001 commercially. The
project has no commercial partners and takes no fees or referrals.

## Dependencies

Each release attaches `pain001-<version>.spdx-licenses.json`, a licence
report for every package in the release environment, and
`pain001-<version>.cdx.json`, the CycloneDX SBOM. The release workflow
installs every optional extra before writing them, so they cover the
full optional dependency tree, not only the base install.

For 0.0.84 the report lists 79 packages. They are under permissive
licences (MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, the Python
Software Foundation licence) with two to note:

- `certifi`, under the Mozilla Public License 2.0, a file-level
  copyleft licence that applies to changes to certifi's own files. The
  optional `otel` extra declares it; it is not part of the base install.
- `cel-python`, whose package metadata declares no licence, so the
  report shows it as unknown. It comes only with the optional `rules`
  extra and is not part of the base install; check its source
  repository before relying on it.

Read the report for the release you install rather than this summary;
it is generated from the release environment each time.
