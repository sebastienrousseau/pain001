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

"""What the pain001 suite is, and how its versions move.

Users install more than one package — `pain001`, `pain001-mcp`,
`pain001-lsp`, a loader or two — and the failure they hit is a version
they cannot reason about: is `pain001-loader-xlsx==0.0.54` supposed to
work with `pain001==0.0.60`?

The suite answers that with a single rule: **every member ships the same
version as the core.** One number describes the whole suite. If the core
is at ``0.0.60`` then so is every wrapper and every loader, and a user
reading two different numbers is reading a mistake rather than a
deliberate difference they need to understand.

Versions advance in ``0.0.1`` steps and stay on the ``0.0.x`` line;
``0.1.0`` follows ``0.0.999``, not ``0.0.60``. A member that jumps off
that line is not signalling independence, it is breaking the one
property this module exists to guarantee.

An earlier revision of this module split the suite in two, versioning
the loaders independently on the grounds that they implement the
published plugin contract rather than the core's internals, so a loader
fix need not wait for a core release. That is a defensible design and it
is not the one this project uses: the cost of a user having to know
which packages track the core and which do not outweighs the cost of an
occasional no-change release. The contract generation in
:data:`~pain001.plugins.PAIN001_API_VERSION` still exists and the
registry still enforces it at load time — it is a safety net, not the
versioning policy.

Three rules follow, and all are checked by
``scripts/check_suite_consistency.py``:

1. Every member's published version must equal the core's.
2. Every member's declared ``pain001`` floor must be a version that
   actually exists, or the combination is uninstallable.
3. Every member's declared ``pain001`` floor follows the policy recorded
   here (:attr:`SuiteMember.floor`). The wrappers (``pain001-mcp``,
   ``pain001-lsp``) are :data:`LOCKSTEP`: they call the core's own API,
   so each release requires the core at the same number. The loaders
   implement the published plugin contract, so each declares the oldest
   core whose contract it needs and keeps it; raising it is a deliberate
   change made in this table, not a side effect of a release. Before
   this rule the floors drifted silently (``>=0.0.55`` on one loader,
   ``>=0.0.56`` on the other, ``>=0.0.70`` on the wrappers) with nothing
   saying which was intended.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, NamedTuple

#: Floor policy for a member whose declared ``pain001`` floor must equal
#: its own version: it uses the core's API, not only the plugin contract.
LOCKSTEP: Final[str] = "lockstep"


class SuiteMember(NamedTuple):
    """One published package in the suite.

    Attributes:
        distribution: The name on PyPI.
        repository: The GitHub repository, ``owner/name``.
        summary: One line, for the README table and error messages.
        floor: The ``pain001`` floor this member must declare:
            :data:`LOCKSTEP` (equal to its own version), an explicit
            version (the oldest core whose plugin contract it needs), or
            ``None`` for the core itself.
    """

    distribution: str
    repository: str
    summary: str
    floor: str | None = LOCKSTEP


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
                summary="Core library and CLI.",
                floor=None,
            ),
            SuiteMember(
                distribution="pain001-mcp",
                repository="sebastienrousseau/pain001-mcp",
                summary="Model Context Protocol server.",
                floor=LOCKSTEP,
            ),
            SuiteMember(
                distribution="pain001-lsp",
                repository="sebastienrousseau/pain001-lsp",
                summary="Language server for payment data files.",
                floor=LOCKSTEP,
            ),
            SuiteMember(
                distribution="pain001-loader-xlsx",
                repository="sebastienrousseau/pain001-loader-xlsx",
                summary="Excel (.xlsx/.xlsm) loader plugin.",
                floor="0.0.56",
            ),
            SuiteMember(
                distribution="pain001-loader-mt101",
                repository="sebastienrousseau/pain001-loader-mt101",
                summary="SWIFT MT101 loader plugin.",
                floor="0.0.55",
            ),
        )
    }
)


def members() -> tuple[SuiteMember, ...]:
    """Return every member of the suite, core first.

    Every member is lockstep, so there is no second accessor to pick a
    subset — the absence of one is the policy.

    Returns:
        All suite members, core first.

    Example:
        >>> [m.distribution for m in members()][0]
        'pain001'
    """
    return tuple(SUITE.values())
