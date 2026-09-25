<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Toolchain and contribution policies

Python 3.10 is the supported floor; CI tests 3.10–3.14 on Linux. Development
uses Python 3.12 and Poetry with the committed lock. No distro-system-Python
compatibility is claimed.

The floor may rise only under [ADR-0004](adr/0004-python-floor-policy.md):
after upstream end-of-life, announced one release ahead and recorded as a
breaking change. Versions advance one step at a time; the maintainer opens
releases. See [stability policy](https://github.com/sebastienrousseau/pain001/blob/main/README.md#stability-guarantees),
[contribution rules](https://github.com/sebastienrousseau/pain001/blob/main/CONTRIBUTING.md) and [governance](https://github.com/sebastienrousseau/pain001/blob/main/GOVERNANCE.md).
