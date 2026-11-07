<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Scope comparison

This is a capability boundary, not an independently researched ranking of
third-party products. No competitor performance or compatibility claim is made.

| Component | Payment XML | Settlement | Synthetic bank reply |
| :--- | :--- | :--- | :--- |
| Core | Bundled pain.001/pain.008 generation, XSD validation | No | pain.002 and camt.053 builders |
| MCP / LSP | Delegate supported operations to core | No | pain.002 / camt.053 parsing tools in the companion pain001-mcp |
| Mockbank | Accept synthetic uploads | No | Rule-driven pain.002 outbox |

Evidence: bundled templates, core generation/parsing modules, and the
[companion implementation inventory](issue-audit.md). Bank acceptance requires
bank-specific evidence beyond schema validation.
