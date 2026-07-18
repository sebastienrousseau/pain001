# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
