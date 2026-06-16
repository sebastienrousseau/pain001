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

"""Language Server (stdio) for Pain001 payment CSV files.

Wraps the pure :mod:`pain001.lsp.diagnostics` engine in a ``pygls`` server
so editors get live IBAN/BIC/currency/charset and missing-column diagnostics
as they type. Run it with ``pain001-lsp`` after ``pip install "pain001[lsp]"``.
"""

from lsprotocol import types as lsp
from pygls.server import LanguageServer

from pain001 import __version__
from pain001.lsp.diagnostics import Diagnostic, diagnostics_for_csv

server = LanguageServer("pain001-lsp", __version__)


def _to_lsp_diagnostic(diagnostic: Diagnostic) -> lsp.Diagnostic:
    """Convert an internal diagnostic to an LSP diagnostic.

    Args:
        diagnostic: The engine-produced diagnostic.

    Returns:
        The equivalent ``lsprotocol`` diagnostic.
    """
    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(
                line=diagnostic.line, character=diagnostic.col_start
            ),
            end=lsp.Position(
                line=diagnostic.line, character=diagnostic.col_end
            ),
        ),
        message=diagnostic.message,
        severity=lsp.DiagnosticSeverity(diagnostic.severity.value),
        code=diagnostic.code,
        source="pain001",
    )


def _publish(ls: LanguageServer, uri: str) -> None:
    """Lint a document and publish its diagnostics to the client.

    Args:
        ls: The active language server.
        uri: URI of the document to lint.
    """
    document = ls.workspace.get_text_document(uri)
    diagnostics = [
        _to_lsp_diagnostic(d) for d in diagnostics_for_csv(document.source)
    ]
    ls.publish_diagnostics(uri, diagnostics)


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(
    ls: LanguageServer, params: lsp.DidOpenTextDocumentParams
) -> None:  # pragma: no cover - thin pygls event binding
    """Lint a document when it is opened.

    Args:
        ls: The active language server.
        params: The open-document notification parameters.
    """
    _publish(ls, params.text_document.uri)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(
    ls: LanguageServer, params: lsp.DidChangeTextDocumentParams
) -> None:  # pragma: no cover - thin pygls event binding
    """Re-lint a document when it changes.

    Args:
        ls: The active language server.
        params: The change-document notification parameters.
    """
    _publish(ls, params.text_document.uri)


def main() -> None:  # pragma: no cover - process entry point
    """Start the language server over stdio."""
    server.start_io()


if __name__ == "__main__":  # pragma: no cover
    main()
