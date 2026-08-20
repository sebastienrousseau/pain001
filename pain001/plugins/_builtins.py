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

"""Adapters that surface the existing loaders as plugin instances.

The existing ``pain001.csv``, ``pain001.json``, ``pain001.db``, and
``pain001.parquet`` modules predate the plugin contract; rather than
rewrite them, this module wraps each in a thin
:class:`pain001.plugins.AbstractLoader`-compatible class and
registers it. Internal callers can keep importing the module
functions; external callers go through the registry.

This deliberately exercises the *exact* same surface external
plugins use, so a regression in the contract is caught against the
built-ins before it can hurt a downstream package.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pain001.plugins._version import PAIN001_API_VERSION
from pain001.plugins.contracts import (
    LoaderResult,
    PluginMeta,
    SchemeFinding,
    SchemeResult,
)

if TYPE_CHECKING:
    from pain001.plugins.registry import PluginRegistry


def _pain001_version() -> str:
    """Return the running pain001's installed version (or ``\"0.0.0\"``)."""
    try:
        return metadata.version("pain001")
    except metadata.PackageNotFoundError:  # pragma: no cover - dev install
        return "0.0.0"


def _make_meta(name: str, description: str) -> PluginMeta:
    """Build a :class:`PluginMeta` for a built-in plugin."""
    return PluginMeta(
        name=name,
        version=_pain001_version(),
        description=description,
        api_version=PAIN001_API_VERSION,
        source="built-in",
    )


class _CsvLoader:
    """Built-in CSV loader wrapping :mod:`pain001.csv.load_csv_data`."""

    meta = _make_meta("csv", "Read flat-record payment data from CSV files.")
    extensions: tuple[str, ...] = (".csv",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire CSV file into a single :class:`LoaderResult`."""
        from pain001.csv.load_csv_data import load_csv_data  # noqa: PLC0415

        rows = load_csv_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_csv_data_streaming``."""
        from pain001.csv.load_csv_data import (  # noqa: PLC0415
            load_csv_data_streaming,
        )

        for chunk in load_csv_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _JsonLoader:
    """Built-in JSON loader wrapping :mod:`pain001.json.load_json_data`."""

    meta = _make_meta(
        "json", "Read flat-record payment data from JSON arrays."
    )
    extensions: tuple[str, ...] = (".json",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire JSON document into a single :class:`LoaderResult`."""
        from pain001.json.load_json_data import load_json_data  # noqa: PLC0415

        rows = load_json_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_json_data_streaming``."""
        from pain001.json.load_json_data import (  # noqa: PLC0415
            load_json_data_streaming,
        )

        for chunk in load_json_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _JsonlLoader:
    """Built-in JSONL loader wrapping :mod:`pain001.json.load_json_data`."""

    meta = _make_meta(
        "jsonl",
        "Read flat-record payment data from newline-delimited JSON files.",
    )
    extensions: tuple[str, ...] = (".jsonl",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire JSONL stream into a single :class:`LoaderResult`."""
        from pain001.json.load_json_data import (
            load_jsonl_data,  # noqa: PLC0415
        )

        rows = load_jsonl_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_jsonl_data_streaming``."""
        from pain001.json.load_json_data import (  # noqa: PLC0415
            load_jsonl_data_streaming,
        )

        for chunk in load_jsonl_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _SqliteLoader:
    """Built-in SQLite loader wrapping :mod:`pain001.db.load_db_data`.

    Reads from the ``pain001`` table; consumers needing a different
    table name should set it via ``--config`` or wrap this loader.
    """

    meta = _make_meta(
        "sqlite",
        "Read flat-record payment data from a SQLite database file.",
    )
    extensions: tuple[str, ...] = (".db", ".sqlite")

    def load(self, path: str) -> LoaderResult:
        """Load every row from the ``pain001`` table at ``path``."""
        from pain001.db.load_db_data import load_db_data  # noqa: PLC0415

        rows = load_db_data(path, table_name="pain001")
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_db_data_streaming``."""
        from pain001.db.load_db_data_streaming import (  # noqa: PLC0415
            load_db_data_streaming,
        )

        for chunk in load_db_data_streaming(path, "pain001", chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


class _ParquetLoader:
    """Built-in Parquet loader (requires the ``pain001[parquet]`` extra)."""

    meta = _make_meta(
        "parquet",
        "Read flat-record payment data from Apache Parquet files "
        "(requires pain001[parquet]).",
    )
    extensions: tuple[str, ...] = (".parquet",)

    def load(self, path: str) -> LoaderResult:
        """Load the entire Parquet file into a single :class:`LoaderResult`."""
        from pain001.parquet.load_parquet_data import (  # noqa: PLC0415
            load_parquet_data,
        )

        rows = load_parquet_data(path)
        return LoaderResult(rows=rows, source_hint=path)

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Yield :class:`LoaderResult` chunks via ``load_parquet_data_streaming``."""
        from pain001.parquet.load_parquet_data import (  # noqa: PLC0415
            load_parquet_data_streaming,
        )

        for chunk in load_parquet_data_streaming(path, chunk_size):
            yield LoaderResult(rows=chunk, source_hint=path)


# ---------------------------------------------------------------------------
# Scheme adapters (whole-batch rulebooks)
# ---------------------------------------------------------------------------
#: Human-readable blurbs for the five bundled scheme profiles, keyed by
#: profile name. Kept beside the adapter rather than in
#: :mod:`pain001.validation.schemes` so the legacy module stays free of
#: plugin concerns.
_SCHEME_DESCRIPTIONS: dict[str, str] = {
    "sepa-sct": "SEPA Credit Transfer rulebook (EUR, IBAN, charset limits).",
    "sepa-sdd": "SEPA Direct Debit rulebook (mandate id, sequence type).",
    "sepa-b2b": "SEPA B2B Direct Debit rulebook (B2B sequence types).",
    "sepa-inst": "SEPA Instant Credit Transfer rulebook (amount ceiling).",
    "xborder-ct": "Cross-border Credit Transfer rulebook (any ISO currency).",
}


def _as_sentence(message: str) -> str:
    """Return ``message`` terminated, as :class:`SchemeFinding` requires.

    The bundled profiles predate the contract and phrase violations
    without a full stop (``"SEPA requires EUR currency (got USD)"``).
    The contract says findings end in a period, and consumers — the
    ``--explain`` renderer, the LSP diagnostic bridge — concatenate
    them with remediation hints, so an unterminated message runs into
    the next sentence.

    Normalising here rather than editing the rulebook keeps the legacy
    strings stable for callers that still read them directly, and puts
    the fix at the one point where legacy shape becomes contract shape.
    """
    stripped = message.rstrip()
    if not stripped or stripped[-1] in ".!?":
        return stripped
    return f"{stripped}."


class _ProfileScheme:
    """Adapt a legacy :class:`ValidationProfile` to :class:`AbstractScheme`.

    The five bundled profiles in :mod:`pain001.validation.schemes`
    predate the plugin contract: they take ``data`` positionally, know
    nothing about ``message_type``, and return a
    :class:`SchemeValidationResult` of :class:`SchemeViolation`. This
    wraps one profile so it presents the same surface an external
    scheme plugin must implement.

    The profile instance is bound once at construction; ``validate``
    does no import work, no dict lookups against the profile registry,
    and allocates exactly one list.

    Args:
        profile: A legacy ``ValidationProfile`` with ``name`` and
            ``validate(data)``.
        description: Blurb shown by ``pain001 plugins list``.
    """

    __slots__ = ("_profile", "meta")

    def __init__(self, profile: Any, description: str) -> None:
        self._profile = profile
        self.meta = _make_meta(profile.name, description)

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        message_type: str,
    ) -> SchemeResult:
        """Run the wrapped profile and translate its violations.

        ``message_type`` is accepted for contract conformance and
        deliberately unused: the bundled profiles are selected by name
        and apply the same rules to every message type they support.
        """
        del message_type  # Contract parameter; profiles are name-selected.
        from pain001.validation.schemes import (  # noqa: PLC0415
            remediation_for,
        )

        legacy = self._profile.validate(rows)
        findings = [
            SchemeFinding(
                row_index=v.index,
                field=v.field,
                rule=v.rule,
                severity=v.severity,
                message=_as_sentence(v.message),
                remediation=remediation_for(v.rule) or None,
            )
            for v in legacy.violations
        ]
        return SchemeResult(is_valid=legacy.is_valid, findings=findings)


# ---------------------------------------------------------------------------
# Writer adapter (where the rendered XML goes)
# ---------------------------------------------------------------------------
class _XmlFileWriter:
    """Built-in writer that puts the rendered XML on the filesystem.

    ``destination`` is a filesystem path. The bytes are written exactly
    as handed over — the contract forbids re-parsing or re-serialising,
    because canonical form is the generator's decision, not the
    writer's.
    """

    __slots__ = ()

    meta = _make_meta(
        "xml-file",
        "Write the rendered ISO 20022 XML to a filesystem path.",
    )

    def write(self, xml: str, destination: str) -> str:
        """Write ``xml`` verbatim to ``destination``; return its real path."""
        target = Path(destination)
        parent = target.parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        target.write_text(xml, encoding="utf-8")
        return str(target.resolve())


_BUILTIN_LOADERS = (
    _CsvLoader,
    _JsonLoader,
    _JsonlLoader,
    _SqliteLoader,
    _ParquetLoader,
)


def register_all(reg: PluginRegistry) -> None:
    """Register every built-in plugin with ``reg``.

    Called by the registry on first lookup so plugin discovery happens
    lazily. Adding a new built-in loader / scheme / writer means
    extending this function (and adding its adapter class above).

    The GPG loader is registered conditionally - only when the
    ``pain001[gpg]`` extra is installed - via
    :func:`pain001.plugins.builtins_gpg.maybe_register`.

    Args:
        reg: The process-level :class:`PluginRegistry` to populate.
    """
    for cls in _BUILTIN_LOADERS:
        reg.register_loader(cls())

    # Scheme profiles. Imported here rather than at module scope so the
    # rulebook module (and its Decimal/regex tables) is only paid for by
    # processes that actually look a plugin up.
    from pain001.validation.schemes import PROFILES  # noqa: PLC0415

    for name, profile in PROFILES.items():
        reg.register_scheme(
            _ProfileScheme(profile, _SCHEME_DESCRIPTIONS.get(name, ""))
        )

    reg.register_writer(_XmlFileWriter())

    # Opt-in built-ins (gated on optional extras).
    from pain001.plugins.builtins_gpg import (  # noqa: PLC0415
        maybe_register as maybe_register_gpg,
    )

    maybe_register_gpg(reg)
