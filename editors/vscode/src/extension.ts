// Copyright (C) 2023-2026 Pain001. All rights reserved.
// Licensed under the Apache License, Version 2.0.
//
// Minimal VS Code client that launches the `pain001-lsp` language server
// (stdio) and lets it provide diagnostics for payment CSV files. The server
// itself lives in Python: `pip install "pain001[lsp]"`.

import { workspace, ExtensionContext } from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient;

export function activate(_context: ExtensionContext): void {
  const command = workspace
    .getConfiguration("pain001")
    .get<string>("serverCommand", "pain001-lsp");

  const serverOptions: ServerOptions = {
    command,
    transport: TransportKind.stdio,
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: "file", language: "csv" }],
  };

  client = new LanguageClient(
    "pain001",
    "Pain001 Language Server",
    serverOptions,
    clientOptions,
  );
  client.start();
}

export function deactivate(): Thenable<void> | undefined {
  return client ? client.stop() : undefined;
}
