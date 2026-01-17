==========================
Frequently Asked Questions
==========================

General Questions
=================

**What is Pain001?**

Pain001 is a Python library for automating ISO 20022-compliant payment file creation. It simplifies the process of generating standardised payment initiation files (pain.001) from CSV or database sources.

**Who should use Pain001?**

Pain001 is designed for:
- Financial institutions processing bulk payments
- Enterprise payment systems
- SEPA and international payment processors
- Accounting software integrations
- Payment automation platforms

**Is Pain001 production-ready?**

Yes! Pain001 has:
- 98.55% test coverage with 568 tests
- Enterprise-grade error handling
- Security best practices (XXE protection, SQL injection prevention)
- Used in production payment systems

**What Python versions are supported?**

Pain001 requires Python 3.9 or higher. It's tested on:
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

**How much does Pain001 cost?**

Pain001 is open-source and completely free under the Apache 2.0 and MIT licences.

Installation & Setup
====================

**How do I install Pain001?**

The easiest way is via pip:

.. code-block:: bash

    pip install pain001

See the `Installation Guide <installation.html>`_ for other methods.

**I get "ModuleNotFoundError: No module named 'pain001'"**

Ensure:
1. You've installed Pain001: `pip install pain001`
2. You're using the correct Python environment
3. The installation completed without errors

Try:

.. code-block:: bash

    pip install --upgrade pain001

**Can I install Pain001 without admin privileges?**

Yes, use the `--user` flag:

.. code-block:: bash

    pip install --user pain001

**Do I need the XSD schema files?**

Yes, XSD schema files are required for validation. Download them from:
- `ISO 20022 UNIFI <https://www.iso20022.org>`_
- Or use the schemas included in your bank's documentation

Usage Questions
===============

**What data sources does Pain001 support?**

Pain001 supports:
- CSV files
- SQLite databases
- Python dictionaries and lists
- Custom data sources (with adapter)

**Do I need to prepare my CSV file?**

Yes, your CSV must have:
- Headers matching the required field names
- Correct data types (strings, numbers, dates)
- Valid IBANs and BICs
- Amounts greater than zero

See `Configuration <configuration.html>`_ for field specifications.

**What ISO 20022 versions does Pain001 support?**

Pain001 supports all major pain.001 versions:
- pain.001.001.03 (SEPA v3)
- pain.001.001.04 (Non-SEPA)
- pain.001.001.05
- pain.001.001.06 (Instant payments)
- pain.001.001.07 (RLP/RTP)
- pain.001.001.08 (TISS)
- pain.001.001.09 (Simplified)
- pain.001.001.10 (Enhanced)
- pain.001.001.11 (Latest)

**Can I process large payment files?**

Yes! Pain001 can handle:
- Batch processing with chunking
- Parallel processing for independent batches
- Streaming from databases
- Memory-efficient processing

See `Examples <examples.html>`_ for batch processing examples.

**How do I process multiple payment files?**

Use a loop or batch processing:

.. code-block:: python

    from pathlib import Path
    from pain001 import main

    for csv_file in Path('payments').glob('*.csv'):
        main(
            xml_message_type='pain.001.001.03',
            xml_template_file_path='template.xml',
            xsd_schema_file_path='pain.001.001.03.xsd',
            data_file_path=str(csv_file)
        )

**Can I use Pain001 without templates?**

No, templates are required. They define:
- XML structure
- Field mappings
- Default values
- Validation rules

Configuration & Templates
=========================

**How do I create a template?**

Templates are XML files that define the structure. See `Configuration <configuration.html>`_ for examples.

**Can I use multiple templates?**

Yes! Create different templates for:
- Different ISO 20022 versions
- Different payment scenarios
- Different business rules

**Where should I store templates?**

Recommended structure:

.. code-block:: text

    project/
    ├── templates/
    │   ├── pain.001.001.03.xml
    │   ├── pain.001.001.06.xml
    │   └── pain.001.001.11.xml
    ├── schemas/
    │   ├── pain.001.001.03.xsd
    │   ├── pain.001.001.06.xsd
    │   └── pain.001.001.11.xsd
    ├── payments/
    │   ├── input/
    │   └── output/
    └── pain001_processor.py

Validation & Errors
===================

**What validation does Pain001 perform?**

Pain001 validates:
- Required fields presence
- Data type correctness
- IBAN/BIC format
- Amount validity (> 0)
- Currency support
- XSD schema compliance
- Business rules

**I get "Validation Error: Invalid IBAN format"**

IBAN format rules:
- Format: 2-letter country code + 2 check digits + account identifier
- Example: DE89370400440532013000 (Germany)
- Must be uppercase
- Total length depends on country (15-34 characters)

Verify with:

.. code-block:: bash

    # Check IBAN format for your country
    # https://en.wikipedia.org/wiki/International_Bank_Account_Number

**I get "XSD Schema Validation Failed"**

Check:
1. Schema file path is correct
2. Schema version matches message type
3. Schema file is valid XML
4. Generated XML structure matches template

**How do I debug validation errors?**

Enable logging:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.DEBUG)

    from pain001 import main
    main(...)  # Detailed error messages will be printed

**Can I skip validation?**

No, validation is mandatory. This ensures compliance and prevents invalid payments.

Payment Processing
==================

**Why is batch booking important?**

Batch booking affects how transactions are grouped:
- **True**: All transactions in one batch (faster processing)
- **False**: Each transaction separate (clearer for reconciliation)

**What's the difference between end-to-end ID and instruction ID?**

- **Instruction ID**: Identifier for the payment instruction (internal use)
- **End-to-End ID**: Used for reconciliation across the entire payment chain

**Can I include remittance information?**

Yes! Remittance info includes:
- Invoice numbers
- Payment references
- Purpose descriptions

Limited to specific character sets per ISO 20022 version.

**What currencies are supported?**

Pain001 supports all ISO 4217 currencies. Most common:
- EUR (SEPA)
- USD, GBP, CHF (International)
- Others as per ISO 20022 standard

Troubleshooting
===============

**Pain001 is processing slowly**

Solutions:
- Process in smaller chunks (1000-2000 records)
- Use parallel processing for independent batches
- Check system resources (CPU, disk)
- Use SSD for database access

**I get "Memory Error" on large files**

Use chunked processing:

.. code-block:: python

    import pandas as pd

    chunks = pd.read_csv('large_file.csv', chunksize=1000)
    for chunk in chunks:
        chunk.to_csv(f'chunk_{i}.csv')
        main(...)  # Process each chunk

**My bank rejects the generated file**

Check:
1. Version matches bank's requirements
2. All required fields are populated
3. IBAN/BIC are correct and active
4. Amounts are valid
5. Currency is correct
6. File validates against XSD

**Can I test without a real bank?**

Yes! Test with:
- Sample data files
- Validation tools
- XSD validators
- Your bank's test environment

Integration
===========

**Can I integrate Pain001 with my application?**

Yes! Pain001 is designed for integration:
- Python API
- Exception handling for errors
- Logging support
- Flexible data input methods

**How do I integrate with a database?**

.. code-block:: python

    from pain001 import main

    # Works directly with SQLite
    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='pain.001.001.03.xsd',
        data_file_path='payments.db'
    )

**Can I use Pain001 in a web application?**

Yes! Example:

.. code-block:: python

    from flask import Flask, request
    from pain001 import main

    app = Flask(__name__)

    @app.route('/generate-payment', methods=['POST'])
    def generate_payment():
        csv_data = request.files['payments']
        try:
            main(...)
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 400

Security
========

**Is Pain001 secure for production use?**

Yes! Pain001 implements:
- XXE attack prevention (defusedxml)
- SQL injection protection (parameterised queries)
- Input validation and sanitization
- Secure error messages (no sensitive data)
- Audit logging

**How is sensitive data handled?**

- Bank details are processed in memory
- Validated before XML generation
- Not logged (unless explicitly enabled for debugging)
- Validated against schema

**Should I store passwords in templates?**

No! Never store sensitive credentials in code or templates. Use:
- Environment variables
- Secure vaults
- Configuration management systems

**How do I enable audit logging?**

.. code-block:: python

    import logging

    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler('audit.log')]
    )

Getting Help
============

**Where can I get help?**

- `Documentation <https://docs.pain001.com/>`_
- `GitHub Issues <https://github.com/sebastienrousseau/pain001/issues>`_
- `GitHub Discussions <https://github.com/sebastienrousseau/pain001/discussions>`_
- `Email <mailto:contact@pain001.com>`_

**How do I report a bug?**

Create an issue on GitHub with:
1. Python version
2. Pain001 version
3. Minimal reproducible example
4. Expected vs actual behaviour
5. Error traceback

**Can I contribute to Pain001?**

Yes! See CONTRIBUTING.md for guidelines.

See Also
========

- `Installation Guide <installation.html>`_
- `Usage Guide <usage.html>`_
- `Configuration <configuration.html>`_
- `Examples <examples.html>`_
- `API Reference <modules.html>`_
