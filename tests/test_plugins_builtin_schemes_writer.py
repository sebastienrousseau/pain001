# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""The bundled scheme profiles and XML writer, as plugins.

Issue #179 requires that `pain001 plugins list` shows "the bundled csv,
sqlite, json, jsonl, parquet loaders, the five scheme profiles, and the
default xml writer, all marked ``source=built-in``". The loaders were
registered from the start; the profiles and the writer were reachable
only through their legacy modules, so the registry listed five entries
where the contract promised eleven.

These tests pin the whole promised set, and pin the adapters' behaviour
— an adapter that registers but mistranslates is worse than one that is
missing, because the contract makes it look authoritative.
"""

from __future__ import annotations

import pathlib

import pytest

from pain001.plugins import (
    AbstractScheme,
    AbstractWriter,
    registry,
)
from pain001.plugins._builtins import _as_sentence

#: Every profile bundled in :mod:`pain001.validation.schemes`.
BUNDLED_SCHEMES = (
    "sepa-sct",
    "sepa-sdd",
    "sepa-b2b",
    "sepa-inst",
    "xborder-ct",
)

#: A row that breaches SEPA-CCY (USD in a EUR-only rulebook).
NON_EUR_ROW = {
    "payment_currency": "USD",
    "debtor_account_IBAN": "DE89370400440532013000",
    "creditor_account_IBAN": "FR1420041010050500013M02606",
    "payment_amount": "100.00",
}


@pytest.mark.parametrize("name", BUNDLED_SCHEMES)
def test_every_bundled_profile_is_registered(name: str) -> None:
    """All five profiles resolve through the registry."""
    assert registry.get_scheme(name) is not None, (
        f"scheme {name!r} is bundled but not registered"
    )


@pytest.mark.parametrize("name", BUNDLED_SCHEMES)
def test_bundled_profiles_satisfy_the_scheme_protocol(name: str) -> None:
    """Adapters must pass the same runtime check external plugins do."""
    assert isinstance(registry.get_scheme(name), AbstractScheme)


@pytest.mark.parametrize("name", BUNDLED_SCHEMES)
def test_bundled_profiles_are_marked_built_in(name: str) -> None:
    """`plugins list` distinguishes bundled from third-party by source."""
    scheme = registry.get_scheme(name)
    assert scheme is not None
    assert scheme.meta.source == "built-in"
    assert scheme.meta.name == name
    assert scheme.meta.description, "a listed plugin needs a description"


def test_default_xml_writer_is_registered_and_built_in() -> None:
    """The default writer is reachable by name, like any other plugin."""
    writer = registry.get_writer("xml-file")
    assert writer is not None
    assert isinstance(writer, AbstractWriter)
    assert writer.meta.source == "built-in"


def test_scheme_adapter_translates_violations_faithfully() -> None:
    """Legacy violations survive the hop to :class:`SchemeFinding`.

    The legacy shape uses ``index``; the contract uses ``row_index``.
    A silent mismatch would point every finding at row 0.
    """
    scheme = registry.get_scheme("sepa-sct")
    assert scheme is not None

    result = scheme.validate([NON_EUR_ROW], message_type="pain.001.001.03")

    assert result.is_valid is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.rule == "SEPA-CCY"
    assert finding.field == "payment_currency"
    assert finding.severity == "error"
    assert finding.row_index == 0
    assert finding.message.endswith("."), "contract: messages end in a period"
    assert finding.remediation, "SEPA-CCY has a remediation hint"


def test_scheme_adapter_reports_the_offending_row_index() -> None:
    """A violation in row 2 must not be reported against row 0."""
    scheme = registry.get_scheme("sepa-sct")
    assert scheme is not None
    clean = dict(NON_EUR_ROW, payment_currency="EUR")

    result = scheme.validate(
        [clean, clean, NON_EUR_ROW], message_type="pain.001.001.03"
    )

    ccy = [f for f in result.findings if f.rule == "SEPA-CCY"]
    assert [f.row_index for f in ccy] == [2]


def test_scheme_adapter_does_not_mutate_the_batch() -> None:
    """The contract forbids implementations mutating ``rows``."""
    scheme = registry.get_scheme("sepa-sct")
    assert scheme is not None
    rows = [dict(NON_EUR_ROW)]
    before = [dict(r) for r in rows]

    scheme.validate(rows, message_type="pain.001.001.03")

    assert rows == before


def test_scheme_adapter_accepts_any_message_type() -> None:
    """``message_type`` is contract surface; profiles are name-selected.

    It must be accepted as keyword-only and must not change the verdict
    for a bundled profile, which is selected by name rather than by
    message type.
    """
    scheme = registry.get_scheme("sepa-sct")
    assert scheme is not None

    a = scheme.validate([NON_EUR_ROW], message_type="pain.001.001.03")
    b = scheme.validate([NON_EUR_ROW], message_type="pain.001.001.09")

    assert [f.rule for f in a.findings] == [f.rule for f in b.findings]


def test_clean_batch_is_valid_with_no_findings() -> None:
    """A conforming batch produces ``is_valid`` and an empty list."""
    scheme = registry.get_scheme("sepa-sct")
    assert scheme is not None
    clean = dict(NON_EUR_ROW, payment_currency="EUR")

    result = scheme.validate([clean], message_type="pain.001.001.03")

    assert result.is_valid is True
    assert result.findings == []


def test_writer_writes_bytes_verbatim(tmp_path: pathlib.Path) -> None:
    """The contract forbids re-parsing or re-serialising the XML."""
    writer = registry.get_writer("xml-file")
    assert writer is not None
    xml = "<?xml version='1.0'?>\n<Document>  <keep-me/>\n</Document>"
    target = tmp_path / "out.xml"

    returned = writer.write(xml, str(target))

    assert target.read_text(encoding="utf-8") == xml
    assert returned == str(target.resolve())


def test_writer_creates_missing_parent_directories(
    tmp_path: pathlib.Path,
) -> None:
    """Writing into a fresh directory tree should not require mkdir first."""
    writer = registry.get_writer("xml-file")
    assert writer is not None
    target = tmp_path / "a" / "b" / "out.xml"

    writer.write("<Doc/>", str(target))

    assert target.exists()


def test_writer_returns_an_absolute_path(tmp_path: pathlib.Path) -> None:
    """The contract asks for a canonical sink identifier."""
    writer = registry.get_writer("xml-file")
    assert writer is not None
    target = tmp_path / "out.xml"

    returned = writer.write("<Doc/>", str(target))

    assert pathlib.Path(returned).is_absolute()


def test_plugins_list_shows_the_full_bundled_set() -> None:
    """Issue #179's acceptance criterion, as a test.

    Five loaders, five schemes, one writer — every one ``built-in``.
    """
    listed = registry.list_plugins()
    by_kind: dict[str, set[str]] = {}
    for info in listed:
        by_kind.setdefault(info.kind, set()).add(info.meta.name)

    assert {"csv", "json", "jsonl", "parquet", "sqlite"} <= by_kind["loader"]
    assert set(BUNDLED_SCHEMES) == by_kind["scheme"]
    assert "xml-file" in by_kind["writer"]
    assert all(
        info.meta.source == "built-in"
        for info in listed
        if info.meta.name in set(BUNDLED_SCHEMES) | {"xml-file"}
    )


class TestSentenceNormalisation:
    """`SchemeFinding` requires a terminated message; legacy rules omit it.

    Consumers concatenate the message with the remediation hint, so an
    unterminated string runs into the sentence that follows it.
    """

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # The real shape: rulebook messages end without punctuation.
            (
                "SEPA requires EUR currency (got USD)",
                "SEPA requires EUR currency (got USD).",
            ),
            ("Already terminated.", "Already terminated."),
            ("Shouty!", "Shouty!"),
            ("Really?", "Really?"),
            ("trailing space ", "trailing space."),
            ("", ""),
            ("   ", ""),
        ],
    )
    def test_messages_are_terminated_exactly_once(
        self, raw: str, expected: str
    ) -> None:
        """Adding a period to an already-terminated message would double it."""
        assert _as_sentence(raw) == expected
