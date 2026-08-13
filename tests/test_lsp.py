# Copyright (C) 2023-2026 Pain001. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Licensed under either of the Apache License, Version 2.0 or the MIT
# License, at your option. See LICENSE-APACHE and LICENSE-MIT.

"""Tests for the Pain001 LSP diagnostics engine and pygls wiring."""

from types import SimpleNamespace

from pain001.lsp.diagnostics import (
    Diagnostic,
    Severity,
    diagnostics_for_csv,
)

# A minimal valid credit-transfer document (header + one clean row).
HEADER = (
    "id,payment_amount,currency,debtor_name,debtor_account_IBAN,"
    "debtor_agent_BIC,creditor_name,creditor_account_IBAN"
)
# Uses genuinely mod-97-valid IBANs so the row lints clean.
GOOD_ROW = (
    "1,150,EUR,Acme Corp,DE89370400440532013000,BANKDEFFXXX,"
    "Globex,DE89370400440532013000"
)


def _codes(text: str, message_type: str = "pain.001.001.03") -> list[str]:
    """Return the diagnostic codes raised for a document.

    Args:
        text: The CSV document text.
        message_type: ISO 20022 message type.

    Returns:
        The list of diagnostic codes.
    """
    return [d.code for d in diagnostics_for_csv(text, message_type)]


class TestDiagnosticsEngine:
    """The pure CSV diagnostic engine."""

    def test_clean_document_has_no_diagnostics(self) -> None:
        """A well-formed document yields no diagnostics."""
        assert diagnostics_for_csv(f"{HEADER}\n{GOOD_ROW}") == []

    def test_empty_document(self) -> None:
        """Empty or header-less input yields no diagnostics."""
        assert diagnostics_for_csv("") == []
        assert diagnostics_for_csv("   \n") == []

    def test_missing_required_columns(self) -> None:
        """Absent core columns are reported on the header line."""
        codes = _codes("id,currency\n1,EUR")
        assert codes.count("missing-column") >= 1
        diags = diagnostics_for_csv("id,currency\n1,EUR")
        assert all(d.line == 0 for d in diags if d.code == "missing-column")

    def test_direct_debit_requires_mandate(self) -> None:
        """pain.008 additionally requires mandate columns."""
        codes = _codes(f"{HEADER}\n{GOOD_ROW}", "pain.008.001.02")
        assert "missing-column" in codes  # mandate_id / sequence_type

    def test_invalid_iban(self) -> None:
        """A malformed IBAN cell raises an invalid-iban error."""
        bad = GOOD_ROW.replace("DE89370400440532013000", "DE00INVALID")
        assert "invalid-iban" in _codes(f"{HEADER}\n{bad}")

    def test_invalid_bic(self) -> None:
        """A malformed BIC cell raises an invalid-bic error."""
        bad = GOOD_ROW.replace("BANKDEFFXXX", "NOTABIC")
        assert "invalid-bic" in _codes(f"{HEADER}\n{bad}")

    def test_invalid_currency(self) -> None:
        """A non-ISO-4217 currency code raises invalid-currency."""
        bad = GOOD_ROW.replace(",EUR,", ",EURO,")
        assert "invalid-currency" in _codes(f"{HEADER}\n{bad}")

    def test_invalid_charset(self) -> None:
        """Characters outside the ISO 20022 Latin set warn."""
        bad = GOOD_ROW.replace("Acme Corp", "Café Solé")
        diags = diagnostics_for_csv(f"{HEADER}\n{bad}")
        charset = [d for d in diags if d.code == "invalid-charset"]
        assert charset
        assert charset[0].severity == Severity.WARNING

    def test_blank_rows_skipped(self) -> None:
        """Entirely blank data rows are ignored."""
        assert diagnostics_for_csv(f"{HEADER}\n{GOOD_ROW}\n,,,,,,,") == []

    def test_empty_cells_skipped(self) -> None:
        """Empty individual cells are skipped, not flagged."""
        row = (
            "1,150,EUR,,DE89370400440532013000,BANKDEFFXXX,"
            "Globex,DE89370400440532013000"
        )
        assert diagnostics_for_csv(f"{HEADER}\n{row}") == []

    def test_diagnostic_span_locates_cell(self) -> None:
        """The reported span covers the offending cell, not the line."""
        bad = GOOD_ROW.replace("DE89370400440532013000", "DE00INVALID")
        diag = next(
            d
            for d in diagnostics_for_csv(f"{HEADER}\n{bad}")
            if d.code == "invalid-iban"
        )
        line_text = bad
        assert line_text[diag.col_start : diag.col_end] == "DE00INVALID"


class TestServerWiring:
    """The pygls server's pure conversion and publish helpers."""

    def test_to_lsp_diagnostic(self) -> None:
        """Internal diagnostics map onto lsprotocol diagnostics."""
        from pain001.lsp.server import _to_lsp_diagnostic

        diag = Diagnostic(
            line=2,
            col_start=3,
            col_end=8,
            severity=Severity.ERROR,
            message="boom",
            code="invalid-iban",
        )
        lsp_diag = _to_lsp_diagnostic(diag)
        assert lsp_diag.range.start.line == 2
        assert lsp_diag.range.start.character == 3
        assert lsp_diag.range.end.character == 8
        assert lsp_diag.severity.value == 1
        assert lsp_diag.code == "invalid-iban"
        assert lsp_diag.source == "pain001"

    def test_publish_collects_and_sends(self) -> None:
        """_publish lints the document and publishes the diagnostics."""
        from pain001.lsp.server import _publish

        bad = GOOD_ROW.replace("DE89370400440532013000", "DE00INVALID")
        document = SimpleNamespace(source=f"{HEADER}\n{bad}")
        captured: dict[str, object] = {}

        ls = SimpleNamespace(
            workspace=SimpleNamespace(get_text_document=lambda uri: document),
            text_document_publish_diagnostics=lambda params: captured.update(
                uri=params.uri, diags=list(params.diagnostics)
            ),
        )
        _publish(ls, "file:///payments.csv")
        assert captured["uri"] == "file:///payments.csv"
        assert any(
            d.code == "invalid-iban"
            for d in captured["diags"]  # type: ignore[attr-defined]
        )

    def test_publish_clean_document(self) -> None:
        """A clean document publishes an empty diagnostic list."""
        from pain001.lsp.server import _publish

        document = SimpleNamespace(source=f"{HEADER}\n{GOOD_ROW}")
        captured: dict[str, object] = {}
        ls = SimpleNamespace(
            workspace=SimpleNamespace(get_text_document=lambda uri: document),
            text_document_publish_diagnostics=lambda params: captured.update(
                diags=list(params.diagnostics)
            ),
        )
        _publish(ls, "file:///clean.csv")
        assert captured["diags"] == []
