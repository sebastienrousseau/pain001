============================
Usage Guide
============================

This guide covers the main use cases and features of Pain001.

Quick Start
===========

The simplest way to use Pain001 is through the `main()` function:

.. code-block:: python

    from pain001 import main

    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd',
        data_file_path='payments.csv'
    )

This will:
1. Load payment data from the CSV file
2. Validate all data against the template requirements
3. Generate an ISO 20022-compliant XML file
4. Validate the XML against the XSD schema

Working with CSV Files
======================

CSV Format
----------

Pain001 expects CSV files with specific columns depending on the ISO 20022 version. For example, pain.001.001.03 requires:

.. csv-table::
   :header: Column Name, Type, Required, Example

   InitiatingParty, string, Yes, Company XYZ
   InitiatingPartyId, string, Yes, INITIATOR001
   PaymentInformationId, string, Yes, PMT001
   BatchBooking, boolean, No, false
   NumberOfTransactions, integer, No, 100
   PaymentBatchAmount, decimal, No, 50000.00
   DebtorName, string, Yes, Acme Corp
   DebtorId, string, Yes, DEBTOR001
   DebtorAccountNumber, string, Yes, IBAN

**Example CSV Structure:**

.. code-block:: text

    InitiatingParty,InitiatingPartyId,PaymentInformationId,DebtorName,DebtorId,...
    Company XYZ,INITIATOR001,PMT001,Acme Corp,DEBTOR001,...
    Company XYZ,INITIATOR001,PMT002,Tech Solutions,DEBTOR002,...

Loading CSV Data
----------------

.. code-block:: python

    from pain001 import main

    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd',
        data_file_path='payments.csv'
    )

Working with SQLite Databases
==============================

Pain001 also supports loading payment data directly from SQLite databases.

Loading Data from SQLite
------------------------

.. code-block:: python

    from pain001 import main

    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd',
        data_file_path='payments.db'  # SQLite database file
    )

Working with Python Data Structures
====================================

You can also work directly with Python dictionaries and lists:

.. code-block:: python

    from pain001.core import Pain001

    payment_data = {
        'InitiatingParty': 'Company XYZ',
        'Transactions': [
            {
                'DebtorName': 'Acme Corp',
                'CreditorName': 'Supplier ABC',
                'Amount': 1000.00,
                # ... other required fields
            },
            # ... more transactions
        ]
    }

    processor = Pain001(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd'
    )

    result = processor.process(payment_data)

Safe Validation (Dry-Run Mode)
===============================

You can validate your data against the ISO 20022 schema **without generating an output file** using the ``--dry-run`` flag. This is ideal for:

- **CI/CD Pipelines:** Pre-flight validation in automated builds
- **Data Quality Checks:** Verify payment data before batch processing
- **Template Development:** Test XML templates and schemas without file clutter
- **Pre-Commit Hooks:** Validate data before committing to version control

Command-Line Usage
------------------

.. code-block:: bash

    python3 -m pain001 \\
        -t pain.001.001.03 \\
        -m templates/pain.001.001.03/template.xml \\
        -s templates/pain.001.001.03/pain.001.001.03.xsd \\
        -d data/payments.csv \\
        --dry-run

**Exit Codes:**

- ``0`` - Validation succeeded (safe to proceed)
- ``1`` - Validation failed (data or schema errors detected)

**What Gets Validated:**

- ✓ XML template structure and syntax
- ✓ XSD schema compliance
- ✓ Payment data integrity (required fields, data types, formats)
- ✓ Business rules (amounts > 0, valid IBANs/BICs, etc.)

Programmatic Dry-Run
--------------------

.. code-block:: python

    from pain001 import process_files

    # Validate without generating XML
    try:
        result = process_files(
            message_type='pain.001.001.03',
            payment_data=my_data,
            xml_template_file_path='template.xml',
            xsd_schema_file_path='schema.xsd',
            dry_run=True  # Validation-only mode
        )
        print("✅ Validation passed")
    except ValueError as e:
        print(f"❌ Validation failed: {e}")

Data Validation
===============

Pain001 automatically validates all data:

**CSV Validation**
- Checks required columns are present (the target version's list from
  the bundled JSON schema, or the 22 columns every version shares)
- Validates data types (strings, numbers, dates)
- Verifies IBAN/BIC formats
- Checks business rules (e.g., amounts > 0)

**Database Validation**
- Validates schema compliance
- Checks data integrity
- Verifies required fields

**XML Validation**
- XSD schema validation
- Business rule validation
- ISO 20022 compliance checks

Validation Example
------------------

.. code-block:: python

    from pain001 import main
    from pain001.exceptions import ValidationError

    try:
        main(
            xml_message_type='pain.001.001.03',
            xml_template_file_path='template.xml',
            xsd_schema_file_path='schema.xsd',
            data_file_path='payments.csv'
        )
        print("✅ Payment file generated successfully!")
    except ValidationError as e:
        print(f"❌ Validation error: {e}")
        print(f"   Details: {e.details}")

Supported ISO 20022 Versions
=============================

Pain001 supports all major pain.001 versions:

.. code-block:: python

    versions = [
        'pain.001.001.03',  # SEPA v3
        'pain.001.001.04',  # Non-SEPA v4
        'pain.001.001.05',  # v5
        'pain.001.001.06',  # Instant payments
        'pain.001.001.07',  # RLP/RTP support
        'pain.001.001.08',  # TISS support
        'pain.001.001.09',  # Simplified
        'pain.001.001.10',  # Enhanced
        'pain.001.001.11',  # Latest
    ]

Each version supports different fields and business rules. Ensure your template and data match your chosen version.

Advanced Configuration
======================

Control batch booking and payment information handling:

.. code-block:: python

    from pain001 import main

    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd',
        data_file_path='payments.csv',
        # Optional parameters can be configured in the template
    )

Error Handling
==============

Pain001 provides specific exception types for different error scenarios:

.. code-block:: python

    from pain001.exceptions import (
        ValidationError,
        XMLGenerationError,
        SchemaValidationError,
        DataLoadError
    )

    try:
        main(
            xml_message_type='pain.001.001.03',
            xml_template_file_path='template.xml',
            xsd_schema_file_path='schema.xsd',
            data_file_path='payments.csv'
        )
    except ValidationError as e:
        print(f"Data validation failed: {e}")
    except XMLGenerationError as e:
        print(f"XML generation failed: {e}")
    except SchemaValidationError as e:
        print(f"XSD validation failed: {e}")
    except DataLoadError as e:
        print(f"Could not load data: {e}")

Common Workflows
================

**Processing Daily Payments**

.. code-block:: python

    from pathlib import Path
    from pain001 import main
    from datetime import datetime

    # Process all CSV files in a directory
    data_dir = Path('payments')
    for csv_file in data_dir.glob('*.csv'):
        output_file = f"payment_{datetime.now().isoformat()}.xml"
        main(
            xml_message_type='pain.001.001.03',
            xml_template_file_path='template.xml',
            xsd_schema_file_path='schema.xsd',
            data_file_path=str(csv_file)
        )
        print(f"✅ Generated: {output_file}")

**Batch Processing from Database**

.. code-block:: python

    from pain001 import main

    # Process payments from multiple database sources
    databases = ['payments_2024.db', 'pending_payments.db']

    for db_file in databases:
        main(
            xml_message_type='pain.001.001.03',
            xml_template_file_path='template.xml',
            xsd_schema_file_path='schema.xsd',
            data_file_path=db_file
        )

Logging and Debugging
=====================

Enable detailed logging to diagnose issues:

.. code-block:: python

    import logging

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('pain001')

    from pain001 import main

    main(
        xml_message_type='pain.001.001.03',
        xml_template_file_path='template.xml',
        xsd_schema_file_path='schema.xsd',
        data_file_path='payments.csv'
    )

Next Steps
==========

- Learn about `Configuration <configuration.html>`_
- See `Examples <examples.html>`_
- Check the `API Reference <modules.html>`_
