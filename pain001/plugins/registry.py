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

"""Process-level plugin registry + entry-point discovery.

Holds one :class:`PluginRegistry` instance per Python process. The
registry is populated lazily on first use:

1. Built-in plugins shipped inside pain001 register first.
2. External plugins discovered via ``importlib.metadata.entry_points``
   register on top, winning over built-ins with the same name.
3. The ``PAIN001_DISABLE_PLUGINS`` env var (comma-separated names)
   skips matching plugins regardless of source - the production
   escape hatch when a plugin breaks.

Plugin authors talk to the registry only through
:func:`pain001.plugins.registry.registry` (the module-level
singleton); inside pain001, the loader / validator / scheme
dispatchers also go through the same singleton so external plugins
and built-ins share one code path.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from importlib import metadata
from typing import Any

from pain001.plugins._version import PAIN001_API_VERSION
from pain001.plugins.contracts import (
    AbstractLoader,
    AbstractScheme,
    AbstractValidator,
    AbstractWriter,
    PluginInfo,
    PluginMeta,
)

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUPS: dict[str, str] = {
    "loader": "pain001.loaders",
    "validator": "pain001.validators",
    "scheme": "pain001.schemes",
    "writer": "pain001.writers",
}


class PluginRegistryError(RuntimeError):
    """Raised when the registry cannot honour a lookup or registration."""


class PluginVersionError(PluginRegistryError):
    """Raised when a plugin declares an API version newer than this build."""


class PluginRegistry:
    """In-process registry of every loaded plugin, keyed by kind + name.

    Not thread-safe for *registration* (plugins are registered once
    at startup and the registry is read-only after); fully safe for
    concurrent lookups thereafter.

    Args:
        api_version: The ``(major, minor)`` tuple the host pain001
            build implements. Plugins declaring a higher *major* are
            refused; plugins declaring a higher *minor* are loaded
            with a warning.
    """

    def __init__(self, api_version: tuple[int, int]) -> None:
        self._api_version = api_version
        self._loaders: dict[str, AbstractLoader] = {}
        self._validators: dict[str, AbstractValidator] = {}
        self._schemes: dict[str, AbstractScheme] = {}
        self._writers: dict[str, AbstractWriter] = {}
        self._disabled = _parse_disabled_env()
        self._populated = False

    # ---------------------------------------------------------------
    # Public lookup API
    # ---------------------------------------------------------------
    def get_loader_for_extension(
        self, extension: str
    ) -> AbstractLoader | None:
        """Return the loader registered for ``extension`` (with leading dot).

        Args:
            extension: File extension to dispatch on, with the leading
                dot, case-insensitive (``".xlsx"``, ``".XLSX"`` both
                work).

        Returns:
            The matching :class:`AbstractLoader`, or ``None`` if none
            is registered.
        """
        self._ensure_populated()
        ext = extension.lower()
        for loader in self._loaders.values():
            if ext in loader.extensions:
                return loader
        return None

    def get_loader(self, name: str) -> AbstractLoader | None:
        """Return the loader registered under ``name`` (or ``None``)."""
        self._ensure_populated()
        return self._loaders.get(name)

    def get_validator(self, name: str) -> AbstractValidator | None:
        """Return the validator registered under ``name`` (or ``None``)."""
        self._ensure_populated()
        return self._validators.get(name)

    def get_scheme(self, name: str) -> AbstractScheme | None:
        """Return the scheme registered under ``name`` (or ``None``)."""
        self._ensure_populated()
        return self._schemes.get(name)

    def get_writer(self, name: str) -> AbstractWriter | None:
        """Return the writer registered under ``name`` (or ``None``)."""
        self._ensure_populated()
        return self._writers.get(name)

    def list_plugins(self, kind: str | None = None) -> list[PluginInfo]:
        """Return a flat list of every registered plugin's metadata.

        Args:
            kind: Optional filter (``"loader"``, ``"validator"``,
                ``"scheme"``, ``"writer"``). When ``None``, every
                kind is included.

        Returns:
            A list of :class:`PluginInfo`, sorted by ``(kind, name)``.
        """
        self._ensure_populated()
        infos: list[PluginInfo] = []
        for k, store in self._stores().items():
            if kind is not None and k != kind:
                continue
            for plugin in store.values():
                infos.append(PluginInfo(kind=k, meta=plugin.meta))
        infos.sort(key=lambda info: (info.kind, info.meta.name))
        return infos

    # ---------------------------------------------------------------
    # Registration API (called by built-ins and entry-point loader)
    # ---------------------------------------------------------------
    def register_loader(self, loader: AbstractLoader) -> None:
        """Register ``loader`` under its declared name; later wins."""
        self._register(loader, self._loaders, kind="loader")

    def register_validator(self, validator: AbstractValidator) -> None:
        """Register ``validator`` under its declared name; later wins."""
        self._register(validator, self._validators, kind="validator")

    def register_scheme(self, scheme: AbstractScheme) -> None:
        """Register ``scheme`` under its declared name; later wins."""
        self._register(scheme, self._schemes, kind="scheme")

    def register_writer(self, writer: AbstractWriter) -> None:
        """Register ``writer`` under its declared name; later wins."""
        self._register(writer, self._writers, kind="writer")

    def reset(self) -> None:
        """Drop every plugin and mark the registry unpopulated again.

        Test-only seam. Production code never resets the singleton.
        """
        self._loaders.clear()
        self._validators.clear()
        self._schemes.clear()
        self._writers.clear()
        self._disabled = _parse_disabled_env()
        self._populated = False

    # ---------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------
    def _stores(self) -> dict[str, dict[str, Any]]:
        """Return the four plugin stores keyed by kind name."""
        return {
            "loader": self._loaders,
            "validator": self._validators,
            "scheme": self._schemes,
            "writer": self._writers,
        }

    def _register(
        self,
        plugin: Any,
        store: dict[str, Any],
        *,
        kind: str,
    ) -> None:
        """Validate ``plugin`` against the contract and stash it in ``store``."""
        meta = getattr(plugin, "meta", None)
        if not isinstance(meta, PluginMeta):
            raise PluginRegistryError(
                f"{kind} plugin {plugin!r} missing a PluginMeta `meta` "
                "attribute"
            )
        if meta.name in self._disabled:
            logger.info(
                "skipping disabled %s plugin %s "
                "(set via PAIN001_DISABLE_PLUGINS)",
                kind,
                meta.name,
            )
            return
        self._check_api_compatibility(meta, kind=kind)
        if meta.name in store and store[meta.name] is not plugin:
            logger.info(
                "%s plugin %s from %s overrides existing %s",
                kind,
                meta.name,
                meta.source,
                store[meta.name].meta.source,
            )
        store[meta.name] = plugin

    def _check_api_compatibility(self, meta: PluginMeta, *, kind: str) -> None:
        """Refuse plugins ahead of the host's major; warn on minor gap."""
        host_major, host_minor = self._api_version
        plugin_major, plugin_minor = meta.api_version
        if plugin_major > host_major:
            raise PluginVersionError(
                f"{kind} plugin {meta.name!r} targets API "
                f"v{plugin_major}.{plugin_minor}, but this pain001 only "
                f"supports up to v{host_major}.{host_minor}; upgrade pain001"
            )
        if (plugin_major, plugin_minor) > (host_major, host_minor):
            logger.warning(
                "%s plugin %s targets API v%d.%d; this pain001 implements "
                "v%d.%d - newer plugin methods may be ignored",
                kind,
                meta.name,
                plugin_major,
                plugin_minor,
                host_major,
                host_minor,
            )

    def _ensure_populated(self) -> None:
        """Lazily register built-ins + entry-point plugins on first lookup."""
        if self._populated:
            return
        self._populated = True  # set before, so re-entrant lookups don't loop
        # Built-ins first; entry-point plugins later (later wins).
        from pain001.plugins import _builtins  # noqa: PLC0415  - lazy

        _builtins.register_all(self)
        _load_entry_point_plugins(self)


def _parse_disabled_env() -> frozenset[str]:
    """Read ``PAIN001_DISABLE_PLUGINS`` into a set of names (or empty)."""
    raw = os.environ.get("PAIN001_DISABLE_PLUGINS", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def _load_entry_point_plugins(reg: PluginRegistry) -> None:
    """Walk each entry-point group and register what we find.

    A plugin that raises during instantiation is skipped with a
    warning so one broken plugin can't take pain001 down. The
    operator can isolate the culprit via ``pain001 plugins list``
    plus the logged plugin name.
    """
    for kind, group in ENTRY_POINT_GROUPS.items():
        for entry in _iter_entry_points(group):
            try:
                plugin_cls = entry.load()
                plugin = plugin_cls()
                # Stamp the source so list_plugins shows the dist name.
                _stamp_source(plugin, entry)
                _register_by_kind(reg, plugin, kind)
            except Exception as exc:  # pragma: no cover - defensive log
                logger.warning(
                    "skipping %s plugin from entry-point %s: %s",
                    kind,
                    entry.name,
                    exc,
                )


def _iter_entry_points(group: str) -> Iterable[metadata.EntryPoint]:
    """Yield entry points for ``group``; tolerate older metadata APIs.

    Python 3.10+ exposes ``EntryPoints.select(...)``; older APIs return
    a ``dict[str, list[EntryPoint]]``. We support both so a plugin
    rollout can't be blocked by an upstream `importlib.metadata`
    shape change.
    """
    eps = metadata.entry_points()
    select = getattr(eps, "select", None)
    if callable(select):
        return select(group=group)
    return eps.get(group, [])  # type: ignore[attr-defined]  # pragma: no cover - legacy


def _stamp_source(plugin: Any, entry: metadata.EntryPoint) -> None:
    """Replace ``meta.source`` with the entry point's distribution name.

    Plugin authors must not set ``source`` themselves; this is the
    one piece of metadata the registry owns so an operator can trust
    it when auditing what's loaded.
    """
    dist = getattr(entry, "dist", None)
    dist_name = getattr(dist, "name", entry.name) or entry.name
    dist_version = getattr(dist, "version", "?") or "?"
    source = f"{dist_name}=={dist_version}"
    # PluginMeta is frozen; rebuild it with the stamped source.
    new_meta = PluginMeta(
        name=plugin.meta.name,
        version=plugin.meta.version,
        description=plugin.meta.description,
        api_version=plugin.meta.api_version,
        source=source,
    )
    object.__setattr__(plugin, "meta", new_meta)


def _register_by_kind(reg: PluginRegistry, plugin: Any, kind: str) -> None:
    """Dispatch to the right ``register_*`` method based on plugin kind."""
    if kind == "loader":
        reg.register_loader(plugin)
    elif kind == "validator":
        reg.register_validator(plugin)
    elif kind == "scheme":
        reg.register_scheme(plugin)
    elif kind == "writer":
        reg.register_writer(plugin)
    else:  # pragma: no cover - defensive
        raise PluginRegistryError(f"unknown plugin kind: {kind!r}")


registry: PluginRegistry = PluginRegistry(PAIN001_API_VERSION)
"""Process-level singleton; everyone reads through this one."""
