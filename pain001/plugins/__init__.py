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

"""Public plugin contract for pain001 v0.0.54+.

Four PEP 544 ``Protocol`` types define the surface any external
package can implement to extend pain001 without forking:

* :class:`AbstractLoader` - read payment rows from a file format
  (CSV, XLSX, encrypted .gpg, etc.).
* :class:`AbstractValidator` - validate parsed rows in isolation
  (schema, types, identifier formats).
* :class:`AbstractScheme` - validate parsed rows against a
  payment-scheme rulebook (SEPA SCT, SDD, instant, custom CEL).
* :class:`AbstractWriter` - serialise generator output (currently
  XML; future: SWIFT MX, JSON, base64-wrapped).

A plugin package is published to PyPI with one or more entry points
in the ``pain001.loaders`` / ``.validators`` / ``.schemes`` /
``.writers`` groups (declared in its ``pyproject.toml``). pain001
discovers them at process start via
``importlib.metadata.entry_points`` and registers each in the
process-level :mod:`pain001.plugins.registry`.

Compatibility
-------------
Every plugin should declare ``PAIN001_API_VERSION = (major, minor)``
as a class attribute. The registry warns (but loads) when the
plugin's declared minor is lower than the running pain001 minor and
refuses to load when the major is higher. This is a stable promise:
within a major version we never break a plugin that compiles against
the published Protocols.

See ``docs/plugins.md`` for the worked example and the contract
versioning policy.
"""

from __future__ import annotations

from pain001.plugins._version import PAIN001_API_VERSION
from pain001.plugins.contracts import (
    AbstractLoader,
    AbstractScheme,
    AbstractValidator,
    AbstractWriter,
    LoaderResult,
    PluginInfo,
    PluginMeta,
    SchemeFinding,
    SchemeResult,
    ValidatorFinding,
    ValidatorResult,
)
from pain001.plugins.registry import (
    PluginRegistry,
    PluginRegistryError,
    PluginVersionError,
    registry,
)

__all__ = [
    "AbstractLoader",
    "AbstractScheme",
    "AbstractValidator",
    "AbstractWriter",
    "LoaderResult",
    "PluginInfo",
    "PluginMeta",
    "PluginRegistry",
    "PluginRegistryError",
    "PluginVersionError",
    "PAIN001_API_VERSION",
    "SchemeFinding",
    "SchemeResult",
    "ValidatorFinding",
    "ValidatorResult",
    "registry",
]
