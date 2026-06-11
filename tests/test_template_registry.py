from pain001.templates import DEFAULT_TEMPLATE_REGISTRY


def test_registry_lists_supported_versions() -> None:
    versions = DEFAULT_TEMPLATE_REGISTRY.list_supported_versions()
    assert "pain.001.001.03" in versions
    assert "pain.001.001.12" in versions
    assert "pain.008.001.02" in versions


def test_registry_resolves_template_paths() -> None:
    template_path, schema_path = DEFAULT_TEMPLATE_REGISTRY.resolve_paths(
        "pain.001.001.12"
    )
    assert template_path.endswith("pain.001.001.12/template.xml")
    assert schema_path.endswith("pain.001.001.12/pain.001.001.12.xsd")


def test_registry_searches_by_category() -> None:
    results = DEFAULT_TEMPLATE_REGISTRY.search_by_category(
        "CustomerCreditTransferInitiation"
    )
    assert any(item.message_type == "pain.001.001.12" for item in results)
