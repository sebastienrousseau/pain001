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

"""Mask account data in the row errors the REST API returns.

A schema error carries the offending value, and jsonschema repeats it in
the message (``'de07...' does not match ...``). For an IBAN, a BIC or a
party name that value is the customer's data, and a response body ends
up in proxies, browser consoles and support tickets. The masking rules
are the log redactor's (:mod:`pain001.logging_schema.redaction`), so a
value is shown the same way in a log line and in an error body.
"""

from __future__ import annotations

from typing import Any

from pain001.logging_schema.redaction import _redact_pii_from_dict

_SENSITIVE_KEYS = ("iban", "bic", "name", "account")
"""Key fragments the log redactor masks; anything else is shown as is."""


def mask_error(field: str, message: str, value: Any) -> tuple[str, str]:
    """Return a row error's message and value with account data masked.

    Args:
        field: The error's JSON path, e.g. ``$.debtor_account_IBAN``.
        message: The validator's message, which may quote the value.
        value: The offending value; a whole row for a row-level error.

    Returns:
        ``(message, value)``: the value as text, masked when the field
        names an IBAN, BIC, account or name (a row is masked field by
        field), and the message with the raw value replaced by it.
    """
    if isinstance(value, dict):
        return message, str(_redact_pii_from_dict(value))
    text = str(value)
    key = field.rsplit(".", 1)[-1]
    if not any(fragment in key.lower() for fragment in _SENSITIVE_KEYS):
        return message, text
    masked = str(_redact_pii_from_dict({key: text})[key])
    return message.replace(text, masked) if text else message, masked
