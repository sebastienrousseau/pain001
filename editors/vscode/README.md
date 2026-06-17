<!-- SPDX-License-Identifier: Apache-2.0 -->

# Pain001 VS Code extension

A thin Language Server Protocol client that surfaces live Pain001
diagnostics — invalid IBAN/BIC/currency cells, characters outside the ISO
20022 Latin set, and missing required columns — directly in the editor as
you edit a payment CSV.

It is a client only: the actual checks run in the Python language server
(`pain001-lsp`), so the same engine backs the editor, the CLI, and CI.

## Prerequisites

```bash
pip install "pain001[lsp]"   # provides the `pain001-lsp` server on PATH
```

## Run from source

```bash
cd editors/vscode
npm install
npm run compile
# Then press F5 in VS Code to launch an Extension Development Host.
```

Open any `.csv` payment file; diagnostics appear inline and in the Problems
panel. Point the extension at a non-default server with the
`pain001.serverCommand` setting (e.g. a virtualenv path).

## Packaging / publishing

Building a `.vsix` and publishing to the Marketplace is an external,
credentialed step (`vsce package` / `vsce publish`) and is intentionally
left to a maintainer with publisher access — it is not part of the Python
package's automated build.
