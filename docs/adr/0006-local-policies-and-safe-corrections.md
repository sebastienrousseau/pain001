<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0006. Local policies and review-only corrections

- Status: Proposed for feat/v0.0.71
- Date: 2026-09-25
- Context: Issues #184–#186 add policy evaluation, repair suggestions and
  delivery at boundaries where silently changing money or trust is unsafe.

## Decision

Use bounded CEL expressions with exact decimal thresholds and request-local
`AbstractScheme` instances. Keep schema validation independent and fail
closed on evaluation errors. An IBAN cannot supply account currency;
require the explicit currency field instead of the requested inference.
National public holidays are a convenience, not settlement-calendar authority.

Follow #185's explicit refusal criterion over its contradictory IBAN-whitespace
example. Suggest patches only for non-financial fields, never apply them,
and require review even when the transformation is deterministic. Source
length bounds from schemas rather than caller-supplied error messages.

Keep SFTP an explicit operation with pre-authentication host-key checking,
no silent trust persistence, same-directory staged publication and byte-hash
retry checks. Do not treat successful delivery as acceptance by a bank.

## Consequences

The optional rules and upload extras keep the base import path unchanged.
Companion MCP tools must run against the matching core feature build before
the coordinated release. The plugin contract and published versions are not
bumped as a side effect. Tests use synthetic records and localhost servers.
