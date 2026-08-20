# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. You may not use this file except in
# compliance with one of those licences. Copies are provided in
# LICENSE-APACHE and LICENSE-MIT.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Licences is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the applicable Licence for the specific language
# governing permissions and limitations.

"""What the pain001 suite is, and which parts move together.

Users install more than one package — `pain001`, `pain001-mcp`,
`pain001-lsp`, a loader or two — and the failure they hit is a version
they cannot reason about: is `pain001-loader-xlsx==0.0.54` supposed to
work with `pain001==0.0.60`?

Two different answers are correct, for two different kinds of package,
and writing them down here is the point of this module.

**Lockstep members** (`pain001-mcp`, `pain001-lsp`) ship the same
version as the core. They wrap the core's own surface, so a core
release is a release for them; a user reading two different numbers is
reading a mistake.

**Plugins** (`pain001-loader-xlsx`, `pain001-loader-mt101`) version
independently. They implement the published plugin contract, not the
core's internals, and a loader bugfix should not wait for a core
release. What binds them is not a matching version number but the
contract generation in :data:`~pain001.plugins.PAIN001_API_VERSION`,
which the registry enforces at load time — a plugin ahead of the host
raises rather than misbehaving.

Two rules follow, and both are checked by
``scripts/check_suite_consistency.py``:

1. A lockstep member's published version must equal the core's.
2. Any member's declared ``pain001`` floor must be a version that
   actually exists, or the combination is uninstallable.

A plugin's own version is deliberately not compared against the core's.
``pain001-loader-mt101`` is at ``0.0.2`` and requires
``pain001>=0.0.55``; that is correct independent versioning, not drift,
and a check that flags it is measuring the wrong thing.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, NamedTuple


class SuiteMember(NamedTuple):
    """One published package in the suite.

    Attributes:
        distribution: The name on PyPI.
        repository: The GitHub repository, ``owner/name``.
        lockstep: Whether its version must equal the core's.
        summary: One line, for the README table and error messages.
    """

    distribution: str
    repository: str
    lockstep: bool
    summary: str


#: The core distribution every other member depends on.
CORE: Final[str] = "pain001"

#: Every published member of the suite, keyed by distribution name.
#:
#: Read-only: this is reference data, and a caller reshaping it would
#: change what a consistency check believes about the world.
SUITE: Final[MappingProxyType[str, SuiteMember]] = MappingProxyType(
    {
        member.distribution: member
        for member in (
            SuiteMember(
                distribution="pain001",
                repository="sebastienrousseau/pain001",
                lockstep=True,
                summary="Core library and CLI.",
            ),
            SuiteMember(
                distribution="pain001-mcp",
                repository="sebastienrousseau/pain001-mcp",
                lockstep=True,
                summary="Model Context Protocol server.",
            ),
            SuiteMember(
                distribution="pain001-lsp",
                repository="sebastienrousseau/pain001-lsp",
                lockstep=True,
                summary="Language server for payment data files.",
            ),
            SuiteMember(
                distribution="pain001-loader-xlsx",
                repository="sebastienrousseau/pain001-loader-xlsx",
                lockstep=False,
                summary="Excel (.xlsx/.xlsm) loader plugin.",
            ),
            SuiteMember(
                distribution="pain001-loader-mt101",
                repository="sebastienrousseau/pain001-loader-mt101",
                lockstep=False,
                summary="SWIFT MT101 loader plugin.",
            ),
        )
    }
)


def lockstep_members() -> tuple[SuiteMember, ...]:
    """Return the members whose version must equal the core's.

    Returns:
        The lockstep members, core first.

    Example:
        >>> [m.distribution for m in lockstep_members()][0]
        'pain001'
    """
    return tuple(m for m in SUITE.values() if m.lockstep)


def plugin_members() -> tuple[SuiteMember, ...]:
    """Return the members that version independently.

    Returns:
        The plugin members.

    Example:
        >>> all(not m.lockstep for m in plugin_members())
        True
    """
    return tuple(m for m in SUITE.values() if not m.lockstep)
