# Custom Validation with JSON Schemas

## Overview

Pain001 validates payment data against **externalized JSON Schemas** (introduced in v0.0.47). This enables:

- **Declarative validation rules** without code changes
- **Multi-version support** (every bundled pain.001 and pain.008 message type)
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
  "required": ["id", "date", "debtor_name"],
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

A schema ships for every bundled message type, as
`pain001/schemas/<message type>.schema.json`: pain.001.001.03 to
pain.001.001.13, pain.008.001.02 and pain.008.001.08. Run `pain001 versions`
for the list.

## Creating Custom Schemas

### Bank-Specific Validation

A custom schema is a complete schema file named `<message type>.schema.json`
in a directory you pass as `schema_dir`. `$ref` to the bundled schema is not
resolved, so start from a copy of the bundled schema and tighten it:

```python
import json
from pathlib import Path

import pain001.schemas
from pain001.validation.schema_validator import SchemaValidator

message_type = "pain.001.001.03"
bundled = Path(pain001.schemas.__file__).parent / f"{message_type}.schema.json"
schema = json.loads(bundled.read_text())

# Tighten the bundled rules for one bank.
schema["title"] = f"Example bank - {message_type}"
schema["properties"]["debtor_agent_BIC"]["pattern"] = "^RZBAATWW.*$"
schema["properties"]["debtor_name"].update(minLength=3, maxLength=60)

# The file must be named <message type>.schema.json.
custom_dir = Path("bank-schemas")
custom_dir.mkdir(exist_ok=True)
(custom_dir / f"{message_type}.schema.json").write_text(json.dumps(schema, indent=2))

validator = SchemaValidator(message_type, schema_dir=custom_dir)
```

Keep custom schemas in your own project, not inside the installed package,
so an upgrade does not remove them.

### Regional Extensions

The same approach restricts a field to one value, for example SEPA-only
payments:

```python
schema["properties"]["service_level_code"]["const"] = "SEPA"
schema["properties"]["currency"]["const"] = "EUR"
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

The original `validate_csv_data()` function still works and, since 0.0.67, reads its required columns from the same schemas through `pain001.validation.required_columns()`. Pass the message type (`validate_csv_data(rows, "pain.001.001.09")`) to get that version's list; with no message type every column all bundled schemas describe is required, which is the historical 22-column contract.

## Performance Notes

- Schema files are loaded once during validator initialization
- Validation is performed efficiently by jsonschema library
- Batch validation optimised for large datasets

## Future Enhancements

Planned features:

1. **pain.002 (Status Reports)** - New schema set
2. **Conditional validation** - Cross-field rules
3. **Custom error messages** - Localization support

## Troubleshooting

### Schema File Not Found

```
ValueError: Invalid message type: pain.001.001.99
FileNotFoundError: Schema validation failed: Path does not exist: .../bank-schemas/pain.001.001.04.schema.json
```

**Solution**: Use a bundled message type (`pain001 versions`), and name a
custom schema `<message type>.schema.json` inside the `schema_dir` you pass.

### Invalid Schema JSON

```
json.JSONDecodeError: Invalid JSON in schema file
```

**Solution**: Validate schema file syntax:

```bash
python -m json.tool bank-schemas/pain.001.001.03.schema.json
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
