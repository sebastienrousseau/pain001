from pain001.templates import validate_registry


def test_template_registry_guardrails_pass_for_bundled_assets() -> None:
    validated = validate_registry()
    assert "pain.001.001.12" in validated
    assert "pain.008.001.02" in validated

