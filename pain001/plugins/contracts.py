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

"""Protocol definitions for the pain001 plugin contract.

Every protocol here is the *minimum* surface a plugin must satisfy
for pain001 to dispatch to it. They are intentionally narrow:

* No mandatory ``__init__`` shape (plugins are instantiated by the
  registry with no arguments, so any plugin needing config reads it
  from environment variables or ``pain001.config``).
* No exceptions are listed as part of the protocol; plugins should
  raise :class:`pain001.exceptions.DataSourceError`,
  :class:`pain001.exceptions.PaymentValidationError`, or any
  subclass thereof. Anything else is treated as a plugin bug.
* All payment data passes through pain001 as ``list[dict[str,
  Any]]`` (flat records); plugins must respect that shape and not
  introduce their own envelopes.

Forward compatibility: when the contract grows a method, it is added
as an *optional* method with a default that calls the existing
surface. We never remove a method inside the same major.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Shared metadata + result types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PluginMeta:
    """Descriptive metadata every plugin must expose.

    Stored on the plugin class as the ``meta`` attribute, surfaced
    by ``pain001 plugins list`` so an operator can audit what the
    running interpreter has loaded. Field semantics:

    * ``name`` - stable, kebab-case identifier (``"csv"``,
      ``"sepa-sct"``). Must be unique within its plugin group; a
      third-party plugin with the same name as a built-in wins.
    * ``version`` - SemVer string of the package shipping the
      plugin (``importlib.metadata.version(...)``).
    * ``description`` - one-line human-readable summary; shown by
      the CLI. Keep under 80 characters.
    * ``api_version`` - ``(major, minor)`` of the pain001 plugin
      contract the plugin targets. Defaults to the current value.
    * ``source`` - ``"built-in"`` for plugins shipped inside
      pain001; ``"<dist-name>==<version>"`` for third-party
      plugins. Auto-filled by the registry; plugins must not set
      it.
    """

    name: str
    version: str
    description: str
    api_version: tuple[int, int] = (0, 54)
    source: str = "built-in"


@dataclass(frozen=True)
class PluginInfo:
    """Lightweight record returned by ``PluginRegistry.list_*`` calls.

    A flattened view of the meta + plugin kind, used by the CLI and
    JSON-RPC inspection tools rather than the live plugin object.
    ``kind`` is one of ``"loader"``, ``"validator"``, ``"scheme"``,
    ``"writer"``; ``meta`` is the plugin's declared
    :class:`PluginMeta`.
    """

    kind: str
    meta: PluginMeta


# ---------------------------------------------------------------------------
# Loader contract
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoaderResult:
    """The two pieces a loader yields on success.

    ``rows`` carries the parsed flat records, one per payment,
    ready for downstream validation and rendering.
    ``source_hint`` is a diagnostic string (typically the original
    file path or ``"<inline>"``) that pain001 attaches to validation
    findings so the user can locate the offending row in the source.
    """

    rows: list[dict[str, Any]]
    source_hint: str = "<inline>"


@runtime_checkable
class AbstractLoader(Protocol):
    """A reader that turns a file path into ``list[dict]`` payment rows.

    Loaders register against one or more file extensions; the
    registry dispatches by suffix at parse time. Required attributes:
    ``meta`` (a :class:`PluginMeta`) and ``extensions`` (a tuple of
    file extensions with leading dot, lower-case, that this loader
    handles - ``(".xlsx", ".xlsm")`` etc.).
    """

    meta: PluginMeta
    extensions: tuple[str, ...]

    def load(self, path: str) -> LoaderResult:
        """Read every row from ``path`` and return them all at once.

        Args:
            path: Absolute or relative filesystem path.

        Returns:
            A :class:`LoaderResult` carrying the parsed rows and a
            source hint (typically the input path).
        """
        ...

    def load_streaming(
        self, path: str, chunk_size: int
    ) -> Iterable[LoaderResult]:
        """Return an iterable of :class:`LoaderResult` chunks.

        Required for ``--streaming`` mode. Loaders that cannot stream
        (e.g. small inline JSON) may return a single-element
        iterable holding every row.

        Args:
            path: Absolute or relative filesystem path.
            chunk_size: Maximum rows per chunk.

        Returns:
            An iterable of :class:`LoaderResult` instances. The
            caller treats each as a self-contained sub-batch.
        """
        ...


# ---------------------------------------------------------------------------
# Validator contract (intra-record, row-by-row)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidatorFinding:
    """A single row-level validation failure.

    Field semantics: ``row_index`` is the zero-based index in the
    input batch where the failure occurred; ``field`` is the field
    name on the row (``"debtor_account_IBAN"``) or ``None`` for
    row-level findings; ``rule`` is the stable kebab-case identifier
    of the rule that failed (``"IBAN-CHECKSUM"``); ``severity`` is
    one of ``"error"``, ``"warning"``, ``"info"``; ``message`` is a
    human-readable explanation ending in a period.
    """

    row_index: int
    field: str | None
    rule: str
    severity: str
    message: str


@dataclass(frozen=True)
class ValidatorResult:
    """Outcome of one validator running against one batch.

    ``is_valid`` is ``True`` only when ``findings`` contains zero
    error-severity entries (warnings do not invalidate).
    ``findings`` is the full list produced by the validator.
    """

    is_valid: bool
    findings: list[ValidatorFinding] = field(default_factory=list)


@runtime_checkable
class AbstractValidator(Protocol):
    """An intra-record validator (one row at a time, no batch context).

    Required attribute: ``meta`` (a :class:`PluginMeta`).
    """

    meta: PluginMeta

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        message_type: str,
    ) -> ValidatorResult:
        """Validate every row independently and return the aggregate.

        Args:
            rows: The full batch the loader produced. Implementations
                must not mutate this list.
            message_type: ISO 20022 message type the validation should
                target (e.g. ``"pain.001.001.09"``).

        Returns:
            A :class:`ValidatorResult` aggregating per-row findings.
        """
        ...


# ---------------------------------------------------------------------------
# Scheme contract (whole-batch rulebook, e.g. SEPA SCT)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SchemeFinding:
    """A single scheme-rulebook violation.

    Same shape as :class:`ValidatorFinding` plus ``related_rows``
    (zero-based indices of other rows the rule relates to, for
    cross-record findings) and an optional ``remediation`` hint
    surfaced by ``--explain``. ``row_index`` is the zero-based
    primary row index; ``field`` is a row field or ``None`` for
    batch-level findings; ``rule`` is a stable kebab-case rule id
    (``"SEPA-CCY"``, ``"DUP-CREDITOR-DATE"``); ``severity`` is one
    of ``"error"`` / ``"warning"`` / ``"info"``; ``message`` ends
    in a period.
    """

    row_index: int
    field: str | None
    rule: str
    severity: str
    message: str
    related_rows: tuple[int, ...] = ()
    remediation: str | None = None


@dataclass(frozen=True)
class SchemeResult:
    """Outcome of one scheme running against one batch.

    ``is_valid`` is ``True`` only when ``findings`` has zero
    error-severity entries; ``findings`` is the list produced by
    the scheme.
    """

    is_valid: bool
    findings: list[SchemeFinding] = field(default_factory=list)


@runtime_checkable
class AbstractScheme(Protocol):
    """A whole-batch rulebook validator (sees every row at once).

    Use this when a rule needs cross-record context (duplicate
    detection, batch totals, BIC reachability against a reference
    list). For row-by-row checks, prefer :class:`AbstractValidator`.
    Required attribute: ``meta`` (a :class:`PluginMeta`).
    """

    meta: PluginMeta

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        message_type: str,
    ) -> SchemeResult:
        """Apply the rulebook to the full batch.

        Args:
            rows: Full batch produced by the loader (and possibly
                pre-filtered by upstream validators). Implementations
                must not mutate this list.
            message_type: ISO 20022 message type the scheme is being
                run against; some rules vary by message type.

        Returns:
            A :class:`SchemeResult` aggregating findings.
        """
        ...


# ---------------------------------------------------------------------------
# Writer contract (serialise the rendered output)
# ---------------------------------------------------------------------------
@runtime_checkable
class AbstractWriter(Protocol):
    """A serialiser that takes the rendered XML and writes it somewhere.

    Default writer writes to a filesystem path; future writers may
    upload to SFTP, push to S3, base64-wrap into a JSON envelope,
    etc. The pivot from "what to render" to "where it goes" lives
    here. Required attribute: ``meta`` (a :class:`PluginMeta`).
    """

    meta: PluginMeta

    def write(self, xml: str, destination: str) -> str:
        """Write ``xml`` to ``destination`` and return the canonical sink.

        Args:
            xml: The validated ISO 20022 XML document, as a string.
                Writers must not re-parse, re-serialise, or alter the
                XML in any way (canonical form is decided by the
                generator).
            destination: Writer-specific location string. The default
                file writer treats this as a filesystem path; an SFTP
                writer would accept ``sftp://user@host/path``; etc.

        Returns:
            A canonical string identifying where the bytes ended up
            (an absolute path, an ``sftp://`` URL, an ``s3://`` URI).
            The caller logs this and returns it from the public API.
        """
        ...
