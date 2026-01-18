# Custom Validation with JSON Schemas

## Overview

Pain001 v0.0.47 introduces **externalized JSON Schemas** for payment data validation. This enables:

- **Declarative validation rules** without code changes
- **Multi-version support** (pain.001.001.03 through 11)
- **Custom bank-specific validation** with schema extensions
- **Clear error messages** with JSON path notation

## Quick Start

### Using the Default Schema

```python
from pain001.validation.schema_validator import SchemaValidator

# Load schema for ISO version
validator = SchemaValidator("pain.001.001.03")

# Validate payment data
data = {
    "id": "MSG001",
    "date": "2024-01-15",
    "debtor_name": "John Doe",
    # ... other required fields
}

errors = validator.validate_data(data)
if errors:
    for error in errors:
        print(f"{error.path}: {error.message}")
else:
    print("✓ Data is valid")
```

### Batch Validation

```python
# Validate multiple rows at once
rows = [row1, row2, row3, ...]
total, valid, errors = validator.validate_batch(rows)

print(f"Valid: {valid}/{total}")
for row_idx, row_errors in errors:
    print(f"Row {row_idx}: {len(row_errors)} errors")
```

## Schema Structure

Each schema file defines:

1. **Required fields**: Must be present in every transaction
2. **Field types**: string, integer, number, boolean
3. **Validation rules**:
   - Length constraints (minLength, maxLength)
   - Numeric ranges (minimum, maximum)
   - Pattern matching (regex for IBAN, BIC, currency codes)
   - Enum validation (allowed values)

Example schema excerpt:
```json
{
  "required": ["id", "date", "debtor_name", ...],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 35,
      "pattern": "^[A-Za-z0-9...]*$"
    },
    "payment_amount": {
      "type": "number",
      "minimum": 0.01,
      "maximum": 999999999.99
    }
  }
}
```

## Error Reporting

Validation errors include:

- **path**: JSON pointer to the invalid field (e.g., `$.debtor_account_IBAN`)
- **message**: Human-readable error description
- **rule**: Validation rule that failed (pattern, required, minimum, etc.)
- **value**: The invalid value

Example error:
```
$.debtor_account_IBAN: 'INVALID123' does not match '^[A-Z]{2}[0-9]{2}[A-Z0-9]+$'
```

## Supported ISO Versions

Schemas are available for all pain.001 versions:

| Version | File | Status |
|---------|------|--------|
| pain.001.001.03 | `pain.001.001.03.schema.json` | ✅ |
| pain.001.001.04 | `pain.001.001.04.schema.json` | ✅ |
| pain.001.001.05 | `pain.001.001.05.schema.json` | ✅ |
| pain.001.001.06 | `pain.001.001.06.schema.json` | ✅ |
| pain.001.001.07 | `pain.001.001.07.schema.json` | ✅ |
| pain.001.001.08 | `pain.001.001.08.schema.json` | ✅ |
| pain.001.001.09 | `pain.001.001.09.schema.json` | ✅ |
| pain.001.001.10 | `pain.001.001.10.schema.json` | ✅ |
| pain.001.001.11 | `pain.001.001.11.schema.json` | ✅ |

## Creating Custom Schemas

### Bank-Specific Validation

Create custom schemas in `pain001/schemas/custom/`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Raiffeisen Austria - pain.001.001.03",
  "type": "object",
  "allOf": [
    { "$ref": "../pain.001.001.03.schema.json" }
  ],
  "properties": {
    "debtor_agent_BIC": {
      "pattern": "^RZBAATWW.*$",
      "description": "Must be Raiffeisen Austria BIC"
    },
    "debtor_name": {
      "minLength": 3,
      "maxLength": 60
    }
  }
}
```

Usage:
```python
validator = SchemaValidator(
    "pain.001.001.03",
    schema_dir=Path("pain001/schemas/custom")
)
```

### Regional Extensions

```json
{
  "title": "SEPA Core - pain.001.001.03",
  "type": "object",
  "allOf": [
    { "$ref": "../pain.001.001.03.schema.json" }
  ],
  "properties": {
    "service_level_code": {
      "const": "SEPA",
      "description": "SEPA payments only"
    },
    "currency": {
      "const": "EUR",
      "description": "EUR currency only"
    }
  }
}
```

## Advanced Usage

### Extracting Required Fields

```python
validator = SchemaValidator("pain.001.001.03")
required_fields = validator.get_required_fields()
print(f"Required fields: {required_fields}")
```

### Getting Field Information

```python
# Get field schema
field_schema = validator.get_field_schema("debtor_account_IBAN")
print(f"IBAN pattern: {field_schema['pattern']}")

# Get field description
description = validator.get_field_description("payment_amount")
print(f"Amount: {description}")
```

### Row-Level Validation

```python
# Validate single row
is_valid, errors = validator.validate_row(row_data)

if is_valid:
    print("✓ Row is valid")
else:
    for error in errors:
        print(f"✗ {error}")
```

## Migration Guide

### From Hardcoded Validation

**Old approach** (hardcoded in Python):
```python
required_columns = ["id", "date", "nb_of_txs", ...]  # Hardcoded

def validate_csv_data(data):
    for row in data:
        for col in required_columns:
            if col not in row:
                raise ValidationError(f"Missing {col}")
```

**New approach** (schema-based):
```python
from pain001.validation.schema_validator import SchemaValidator

validator = SchemaValidator("pain.001.001.03")
errors = validator.validate_data(row)
if errors:
    raise ValidationError(errors)
```

### Backward Compatibility

The original `validate_csv_data()` function still works but is now powered by schemas internally.

## Performance Notes

- Schema files are loaded once during validator initialization
- Validation is performed efficiently by jsonschema library
- Batch validation optimised for large datasets

## Future Enhancements

Planned features:

1. **pain.008 (Direct Debit)** - Drop in schema file
2. **pain.002 (Status Reports)** - New schema set
3. **Conditional validation** - Cross-field rules
4. **Custom error messages** - Localization support

## Troubleshooting

### Schema File Not Found

```
FileNotFoundError: Schema file not found: pain001/schemas/invalid.schema.json
```

**Solution**: Check message type format is correct (e.g., `pain.001.001.03`)

### Invalid Schema JSON

```
json.JSONDecodeError: Invalid JSON in schema file
```

**Solution**: Validate schema file syntax:
```bash
python -m json.tool pain001/schemas/custom/my_schema.json
```

### Unexpected Validation Failures

Enable detailed error reporting:
```python
for error in errors:
    print(f"Path: {error.path}")
    print(f"Rule: {error.rule}")
    print(f"Message: {error.message}")
    print(f"Value: {error.value}")
```

## References

- [JSON Schema Specification](https://json-schema.org/)
- [ISO 20022 Standards](https://www.iso20022.org/)
- [SEPA Rulebook](https://www.europeanpaymentscouncil.eu/)
