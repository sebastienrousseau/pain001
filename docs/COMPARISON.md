<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Scope comparison

This is a capability boundary, not an independently researched ranking of
third-party products. No competitor performance or compatibility claim is made.

| Component | Payment XML | Settlement | Synthetic bank reply |
| :--- | :--- | :--- | :--- |
| Core | Bundled pain.001/pain.008 generation, XSD validation | No | pain.002 builder |
| MCP / LSP | Delegate supported operations to core | No | MCP parsing tools |
| Mockbank | Accept synthetic uploads | No | Rule-driven pain.002 outbox |

Evidence: bundled templates, core generation/parsing modules, and the
[companion implementation inventory](issue-audit.md). Bank acceptance requires
bank-specific evidence beyond schema validation.
