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

"""PII redaction and log-injection sanitization (GDPR/PCI-DSS, CWE-117)."""

from typing import Any


def mask_sensitive_data(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive data for logging.

    Args:
        value: The sensitive value to mask.
        visible_chars: Number of characters to show at start and end.

    Returns:
        Masked string showing only first and last visible_chars.

    Examples:
        >>> mask_sensitive_data("GB29NWBK60161331926819", 4)
        'GB29****6819'
        >>> mask_sensitive_data("Short", 4)
        '****'
    """
    if len(value) <= visible_chars * 2:
        return "****"
    masked_length = len(value) - (visible_chars * 2)
    return (
        f"{value[:visible_chars]}{'*' * masked_length}{value[-visible_chars:]}"
    )


def _sanitize_value(value: Any) -> Any:
    """Sanitize value to prevent log injection (remove newlines)."""
    if isinstance(value, str):
        return value.replace("\n", "").replace("\r", "")
    return value


def _redact_pii_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Redact PII from dictionary fields recursively.

    This function implements GDPR/PCI-DSS compliant logging by automatically
    masking sensitive fields before they reach log aggregation systems.

    It also sanitizes all string values to prevent log injection (CWE-117).

    Redacted fields:
    - *iban* (any key containing 'iban'): Shows first 4 + last 4 chars
    - *bic* (any key containing 'bic'): Shows first 4 + last 2 chars
    - *name* (any key containing 'name'): Replaced with [REDACTED]
    - *account* (any key containing 'account'): Shows first 4 + last 4 chars

    Args:
        data: Dictionary that may contain PII fields.

    Returns:
        New dictionary with PII fields redacted and strings sanitized.

    Example:
        >>> _redact_pii_from_dict({"debtor_iban": "GB29NWBK60161331926819"})
        {'debtor_iban': 'GB29****6819'}
    """
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()

        if isinstance(value, dict):
            redacted[key] = _redact_pii_from_dict(value)
        elif isinstance(value, list):
            redacted[key] = [
                (
                    _redact_pii_from_dict(item)
                    if isinstance(item, dict)
                    else _sanitize_value(item)
                )
                for item in value
            ]
        elif "iban" in key_lower and isinstance(value, str):
            redacted[key] = mask_sensitive_data(
                _sanitize_value(value), visible_chars=4
            )
        elif "bic" in key_lower and isinstance(value, str):
            val = _sanitize_value(value)
            redacted[key] = (
                f"{val[:4]}**{val[-2:]}" if len(val) > 6 else "****"
            )
        elif "name" in key_lower and isinstance(value, str):
            redacted[key] = "[REDACTED]"
        elif "account" in key_lower and isinstance(value, str):
            redacted[key] = mask_sensitive_data(
                _sanitize_value(value), visible_chars=4
            )
        else:
            redacted[key] = _sanitize_value(value)

    return redacted
