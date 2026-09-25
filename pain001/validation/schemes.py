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

"""Stable scheme API and plugin dispatch, separate from pure built-in rules."""

from typing import Any

from pain001.observability.otel import set_span_attributes, traced
from pain001.validation._scheme_rules import (
    PROFILES as PROFILES,
)
from pain001.validation._scheme_rules import (
    REMEDIATIONS as REMEDIATIONS,
)
from pain001.validation._scheme_rules import (
    AntiDuplicateProfile as AntiDuplicateProfile,
)
from pain001.validation._scheme_rules import (
    CrossBorderCreditTransferProfile as CrossBorderCreditTransferProfile,
)
from pain001.validation._scheme_rules import (
    SchemeValidationResult as SchemeValidationResult,
)
from pain001.validation._scheme_rules import (
    SchemeViolation as SchemeViolation,
)
from pain001.validation._scheme_rules import (
    SepaB2BDirectDebitProfile as SepaB2BDirectDebitProfile,
)
from pain001.validation._scheme_rules import (
    SepaCreditTransferProfile as SepaCreditTransferProfile,
)
from pain001.validation._scheme_rules import (
    SepaDirectDebitProfile as SepaDirectDebitProfile,
)
from pain001.validation._scheme_rules import (
    SepaInstantCreditTransferProfile as SepaInstantCreditTransferProfile,
)
from pain001.validation._scheme_rules import (
    ValidationProfile as ValidationProfile,
)
from pain001.validation._scheme_rules import (
    _duplicate_key as _duplicate_key,
)
from pain001.validation._scheme_rules import (
    _minor_units as _minor_units,
)
from pain001.validation._scheme_rules import (
    remediation_for as remediation_for,
)


def _split_profile_spec(profile: str) -> list[str]:
    """Split a profile spec into distinct names, first occurrence first.

    Args:
        profile: One profile name, or several separated by commas
            (``"sepa-sct,anti-duplicate"``). Whitespace around names is
            ignored; repeated names are kept once.

    Returns:
        The distinct names in order (possibly empty for a blank spec).
    """
    names: list[str] = []
    for raw in profile.split(","):
        name = raw.strip()
        if name and name not in names:
            names.append(name)
    return names


@traced("pain001.validate.scheme")
def validate_scheme(
    data: list[dict[str, Any]],
    profile: str = "sepa-sct",
    *,
    message_type: str = "pain.001.001.03",
) -> SchemeValidationResult:
    """Validate payment rows against a named scheme profile.

    Args:
        data: Loaded payment rows (the normalised internal form).
        profile: Profile name to apply (default: ``"sepa-sct"``), or a
            comma-separated list of names (``"sepa-sct,anti-duplicate"``)
            to run several rulebooks and report the union of their
            findings. The combined result's ``profile`` joins the names
            with commas and its violations are ordered by row.
        message_type: Message type passed to registered scheme plugins.

    Returns:
        A :class:`SchemeValidationResult` listing every violation.

    Raises:
        ValueError: If ``profile`` names a profile that is not registered.

    Example:
        >>> rows = [{
        ...     "payment_currency": "USD",
        ...     "debtor_account_IBAN": "DE89370400440532013000",
        ...     "creditor_account_IBAN": "FR1420041010050500013M02606",
        ...     "payment_amount": "100.00",
        ... }]
        >>> result = validate_scheme(rows, profile="sepa-sct")
        >>> result.is_valid
        False
        >>> result.violations[0].rule
        'SEPA-CCY'
        >>> both = validate_scheme(rows * 2, profile="sepa-sct,anti-duplicate")
        >>> both.profile
        'sepa-sct,anti-duplicate'
    """
    from pain001.plugins._builtins import _ProfileScheme
    from pain001.plugins.registry import registry as plugin_registry

    names = _split_profile_spec(profile)
    registered = {
        name: plugin
        for name in names
        if (plugin := plugin_registry.get_scheme(name)) is not None
    }
    unknown = [name for name in names if name not in registered]
    if not names or unknown:
        available = ", ".join(
            info.meta.name for info in plugin_registry.list_plugins("scheme")
        )
        offending = unknown[0] if unknown else profile
        raise ValueError(
            f"Unknown scheme profile '{offending}'. Available: {available}"
        )
    set_span_attributes(
        **{
            "pain001.scheme": ",".join(names),
            "pain001.row_count": len(data),
        }
    )
    combined = SchemeValidationResult(profile=",".join(names))
    for chosen in registered.values():
        if isinstance(chosen, _ProfileScheme):
            # Retain legacy punctuation while using the registered adapter.
            combined.violations.extend(chosen.validate_legacy(data).violations)
        else:
            result = chosen.validate(data, message_type=message_type)
            combined.violations.extend(
                SchemeViolation(
                    index=f.row_index,
                    field=f.field,
                    rule=f.rule,
                    message=f.message,
                    severity=f.severity,
                )
                for f in result.findings
            )
    combined.violations.sort(key=lambda v: v.index)
    return combined
