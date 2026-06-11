from hypothesis import given
from hypothesis import strategies as st

from pain001.csv.validate_csv_data import (
    _validate_field_type,
    validate_csv_data,
)
from pain001.validation.bic_validator import validate_bic
from pain001.validation.iban_validator import validate_iban

SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        min_codepoint=48,
        max_codepoint=122,
    ),
    min_size=1,
    max_size=20,
)


@given(st.text(min_size=0, max_size=40))
def test_iban_validator_never_crashes(candidate: str) -> None:
    validate_iban(candidate, strict=False)


@given(st.text(min_size=0, max_size=20))
def test_bic_validator_never_crashes(candidate: str) -> None:
    validate_bic(candidate, strict=False)


@given(st.text(min_size=0, max_size=30))
def test_float_field_validation_never_crashes(candidate: str) -> None:
    _validate_field_type(candidate, float)


@given(
    st.fixed_dictionaries(
        {
            "id": st.integers(min_value=1, max_value=99999).map(str),
            "date": st.just("2026-01-01T00:00:00"),
            "nb_of_txs": st.just("1"),
            "ctrl_sum": st.just("1.00"),
            "initiator_name": SAFE_TEXT,
            "payment_information_id": SAFE_TEXT,
            "payment_method": st.just("TRF"),
            "batch_booking": st.sampled_from(["true", "false"]),
            "service_level_code": st.just("SEPA"),
            "requested_execution_date": st.just("2026-01-02"),
            "debtor_name": SAFE_TEXT,
            "debtor_account_IBAN": st.just("DE89370400440532013000"),
            "debtor_agent_BIC": st.just("DEUTDEFF"),
            "forwarding_agent_BIC": st.just("DEUTDEFF"),
            "charge_bearer": st.just("SLEV"),
            "payment_id": SAFE_TEXT,
            "payment_amount": st.just("1.00"),
            "currency": st.just("EUR"),
            "creditor_agent_BIC": st.just("DEUTDEFF"),
            "creditor_name": SAFE_TEXT,
            "creditor_account_IBAN": st.just("DE89370400440532013000"),
            "remittance_information": SAFE_TEXT,
        }
    )
)
def test_validate_csv_data_property_on_complete_rows(
    row: dict[str, str],
) -> None:
    assert validate_csv_data([row]) is True
