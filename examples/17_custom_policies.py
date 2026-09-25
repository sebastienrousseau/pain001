# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Exercise request-local CEL rules, exact boundaries and fail-closed errors.

Run with the rules extra installed: poetry run python examples/17_custom_policies.py.
These rules flag matching rows; they never change payment data.
"""

from copy import deepcopy

from pain001.validation.policy import CustomRuleScheme, validate_policy

RULES = """
- id: REVIEW-LIMIT
  where: 'payment_amount > decimal("50000.00")'
  severity: error
  message: Review the payment before approval.
"""


def main() -> None:
    """Verify exact thresholds, unchanged inputs and isolated rule evaluation."""
    rows = [{"payment_amount": "50000.00"}, {"payment_amount": "50000.01"}]
    original = deepcopy(rows)
    result = CustomRuleScheme(RULES).validate(
        rows, message_type="pain.001.001.03"
    )
    assert not result.is_valid
    assert [(f.row_index, f.rule) for f in result.findings] == [
        (1, "REVIEW-LIMIT")
    ]
    assert rows == original
    assert validate_policy(rows, RULES.replace("error", "warning")).is_valid
    assert validate_policy(
        rows, RULES.replace("50000.00", "60000.00")
    ).is_valid
    try:
        validate_policy([{}], RULES)
    except ValueError as error:
        assert "evaluation failed" in str(error)
    else:
        raise AssertionError("Missing policy fields must fail closed")
    try:
        CustomRuleScheme(RULES.replace('decimal("50000.00")', "50000.01"))
    except ValueError as error:
        assert "floating-point" in str(error)
    else:
        raise AssertionError("Inexact policy literals must be rejected")
    print("CEL boundaries, warnings, isolation and fail-closed errors: passed")


if __name__ == "__main__":
    main()
