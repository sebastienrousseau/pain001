# Python API Contract Testing Tollgate

## Mission

Enforce 100% backward compatibility and API stability for payment processing.

## Tollgate Objectives

- Enforce **zero breaking changes** without MAJOR version bump
- Validate **all 4 input sources** (CSV, SQLite, List, Dict) work identically
- Validate **all 9 ISO versions** (v03-v11) produce valid XML
- Ensure **function signatures** never change without deprecation

## When This Tollgate Applies

- Modifying `pain001/core/core.py` (public API)
- Changing function signatures in `pain001/` modules
- Modifying XML templates
- Changing validation logic
- Updating dependencies

## Tollgate Checks

### 1. Contract Test Suite (MANDATORY)

```bash
# Run contract tests
poetry run pytest tests/test_contracts.py -v

# Expected: All contracts validated
# - Input source parity: CSV == SQLite == List == Dict
# - ISO version outputs: All 9 versions validate against XSD
# - Function signatures: All public APIs unchanged
```

**Success Criteria:**

- All 4 input sources produce byte-identical XML (excluding timestamps)
- All 9 ISO versions pass XSD validation
- No function signature changes detected
- Deprecation warnings display correctly

### 2. Golden File Testing (XML Output Validation)

```bash
# Generate golden files (baseline)
poetry run python scripts/generate_golden_files.py

# Verify against golden files
poetry run pytest tests/test_golden_files.py --golden-diff

# Any differences? Manual review required.
```

**Success Criteria:**

- Generated XML matches golden files byte-for-byte
- Schema validation passes for all versions
- No unexpected field changes

### 3. Input Source Parity (MANDATORY)

```bash
# Test all 4 input sources produce identical output
poetry run pytest tests/test_input_parity.py -v

# Validates:
# - CSV file → XML
# - SQLite DB → XML
# - Python list → XML
# - Python dict → XML
# All produce same XML (modulo timestamps)
```

**Success Criteria:**

- SHA256 hash identical for all 4 sources
- Field ordering consistent
- Data types preserved correctly

### 4. Deprecation Warnings (Breaking Change Prevention)

```python
# Check for proper deprecation warnings
import warnings
warnings.simplefilter("error", DeprecationWarning)

# Run tests - should NOT raise DeprecationWarning unless intentional
poetry run pytest tests/ -W error::DeprecationWarning
```

**Success Criteria:**

- No unexpected deprecation warnings
- Deprecated features show clear migration path
- Deprecations documented in CHANGELOG

### 5. Type Contract Validation (Static Analysis)

```bash
# Verify public API type hints are stable
poetry run python scripts/check_api_contracts.py

# Checks:
# - Function signatures unchanged
# - Return types consistent
# - Exception types documented
```

**Success Criteria:**

- No signature changes without version bump
- Type hints complete and accurate
- Exceptions documented

## Red Lines (NEVER Violate)

- ❌ NEVER change function signatures without deprecation cycle
- ❌ NEVER make CSV/SQLite/List/Dict behave differently
- ❌ NEVER break XSD validation for any ISO version
- ❌ NEVER change field ordering without major version bump
- ❌ NEVER remove public APIs without 2+ release deprecation

## Contract Test Template

```python
# tests/test_contracts.py
import pytest
from pain001.core.core import process_files
import hashlib

@pytest.mark.parametrize("input_source", [
    "tests/fixtures/payment_data.csv",
    "tests/fixtures/payment_data.db",
    pytest.param([{"id": "001", ...}], id="python-list"),
    pytest.param({"id": "001", ...}, id="python-dict"),
])
def test_input_source_parity(input_source, tmp_path):
    """All 4 input sources produce identical XML."""
    output = tmp_path / "output.xml"
    
    result = process_files(
        xml_message_type="pain.001.001.03",
        data_path=input_source,
        output_file_path=str(output)
    )
    
    # Normalize timestamps (they vary)
    xml = output.read_text()
    xml_normalized = normalize_timestamps(xml)
    
    # Hash should be identical
    hash_val = hashlib.sha256(xml_normalized.encode()).hexdigest()
    
    # Store first hash, compare subsequent
    if not hasattr(test_input_source_parity, "baseline_hash"):
        test_input_source_parity.baseline_hash = hash_val
    else:
        assert hash_val == test_input_source_parity.baseline_hash


@pytest.mark.parametrize("version", [
    "pain.001.001.03", "pain.001.001.04", "pain.001.001.05",
    "pain.001.001.06", "pain.001.001.07", "pain.001.001.08",
    "pain.001.001.09", "pain.001.001.10", "pain.001.001.11",
])
def test_iso_version_xsd_validation(version, tmp_path):
    """All 9 ISO versions pass XSD validation."""
    output = tmp_path / f"output_{version}.xml"
    
    result = process_files(
        xml_message_type=version,
        data_path="tests/fixtures/payment_data.csv",
        output_file_path=str(output)
    )
    
    # XSD validation should pass
    assert result is not None
    assert output.exists()
    
    # Validate against XSD
    from pain001.xml.validate_via_xsd import validate_via_xsd
    xsd_path = f"pain001/templates/{version}/{version}.xsd"
    is_valid = validate_via_xsd(str(output), xsd_path)
    assert is_valid, f"{version} failed XSD validation"


def test_process_files_signature_unchanged():
    """Public API signature must not change."""
    import inspect
    from pain001.core.core import process_files
    
    sig = inspect.signature(process_files)
    params = list(sig.parameters.keys())
    
    # Expected signature (v0.0.44 baseline)
    expected_params = [
        "xml_message_type",
        "data_path",
        "xml_template_file_path",
        "xsd_schema_file_path",
        "output_file_path"
    ]
    
    assert params == expected_params, \
        f"API contract broken! Expected {expected_params}, got {params}"


def test_backward_compatibility_v0_0_43():
    """Ensure v0.0.44 can read v0.0.43 generated files."""
    # Load XML generated by v0.0.43
    old_xml_path = "tests/fixtures/v0_0_43_output.xml"
    
    # Should still validate
    from pain001.xml.validate_via_xsd import validate_via_xsd
    is_valid = validate_via_xsd(
        old_xml_path,
        "pain001/templates/pain.001.001.03/pain.001.001.03.xsd"
    )
    assert is_valid, "Backward compatibility broken with v0.0.43"
```

## Golden File Generation Script

```python
# scripts/generate_golden_files.py
"""Generate golden XML files for contract testing."""
from pain001.core.core import process_files
from pathlib import Path

VERSIONS = [
    "pain.001.001.03", "pain.001.001.04", "pain.001.001.05",
    "pain.001.001.06", "pain.001.001.07", "pain.001.001.08",
    "pain.001.001.09", "pain.001.001.10", "pain.001.001.11",
]

def main():
    golden_dir = Path("tests/golden_files")
    golden_dir.mkdir(exist_ok=True)
    
    for version in VERSIONS:
        output = golden_dir / f"{version}.xml"
        process_files(
            xml_message_type=version,
            data_path="tests/fixtures/payment_data.csv",
            output_file_path=str(output)
        )
        print(f"✓ Generated golden file: {output}")

if __name__ == "__main__":
    main()
```

## Semantic Versioning Enforcement

```bash
# Check for breaking changes
poetry run python scripts/check_breaking_changes.py

# Detects:
# - Function signature changes
# - Removed public APIs
# - Changed return types
# - Modified exceptions

# Exit code:
# 0 = No breaking changes (patch/minor bump ok)
# 1 = Breaking changes detected (major bump required)
```

## Integration with CI/CD

```yaml
# .github/workflows/contracts.yml
name: 🤝 API Contract Tests

on: [push, pull_request]

jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Contract Tests
        run: poetry run pytest tests/test_contracts.py -v
      
      - name: Check Breaking Changes
        run: poetry run python scripts/check_breaking_changes.py
        # Fails if breaking changes detected without version bump
      
      - name: Validate Golden Files
        run: poetry run pytest tests/test_golden_files.py --golden-diff
```

## Why This Matters

- **User Trust**: Breaking changes without notice destroy trust
- **Ecosystem Stability**: Downstream users depend on API stability
- **ISO Compliance**: Payment files MUST conform to specs
- **Data Integrity**: Different inputs must produce consistent outputs

## Escalation Path

If contract tests fail:

1. **STOP** - Do not proceed
2. **Classify** - Is this a breaking change?
3. **If breaking**:
   - Bump MAJOR version (v0.0.44 → v1.0.0)
   - Document in CHANGELOG with migration guide
   - Add deprecation warnings in current version
4. **If non-breaking**:
   - Fix code to maintain compatibility
   - Update tests if assumptions changed

## Success Metrics

- Zero accidental breaking changes
- 100% input source parity maintained
- All 9 ISO versions always valid
- No user-reported compatibility issues
