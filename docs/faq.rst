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

CI enforces 100% line and branch coverage and security checks. Passing
those gates is not certification for a bank or production deployment;
validate your bank-specific requirements and operational controls.

**What Python versions are supported?**

Pain001 requires Python 3.11 or higher. CI tests Python 3.11–3.14 on Linux;
development uses Python 3.12. See the toolchain policy for floor changes.

**How much does Pain001 cost?**

Pain001 is open source and free, dual-licensed under Apache-2.0 OR MIT at your option.

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

No. Every bundled message type ships with its XSD, and the CLI resolves it
automatically. Pass ``-s`` / ``--schema`` only to validate against a
different schema, such as one from your bank.

Usage Questions
===============

**What data sources does Pain001 support?**

Pain001 supports:

- CSV files
- SQLite databases
- JSON and JSON Lines files
- Parquet files (``parquet`` extra)
- GPG-encrypted wrappers of these (``gpg`` extra)
- Python dictionaries and lists
- Other formats through loader plugins, such as ``pain001-loader-xlsx``

**Do I need to prepare my CSV file?**

Yes, your CSV must have:
- Headers matching the required field names
- Correct data types (strings, numbers, dates)
- Valid IBANs and BICs
- Amounts greater than zero

See `Configuration <configuration.html>`_ for field specifications.

**What ISO 20022 versions does Pain001 support?**

Pain001 bundles pain.001.001.03 to pain.001.001.13 and the pain.008.001.02
and pain.008.001.08 direct debits. Run ``pain001 versions`` for the list the
installed build supports.

**Can I process large payment files?**

Yes. Pain001 can:

- Stream the input in chunks and write one XML file per chunk
  (``--streaming --chunk-size``)
- Write a large file with constant memory (``stream_xml_to_file``)

There is no built-in parallelism; run independent batches in separate
processes if you need it.

See `Examples <examples.html>`_ for batch processing examples.

**How do I process multiple payment files?**

Use a loop or batch processing:

.. code-block:: python

    from pathlib import Path

    from pain001 import process_files
    from pain001.constants import TEMPLATES_DIR

    message_type = "pain.001.001.03"
    bundle = TEMPLATES_DIR / message_type
    Path("output").mkdir(exist_ok=True)

    # From Python, data files must be under the current working directory.
    for csv_file in sorted(Path("payments").glob("*.csv")):
        process_files(
            xml_message_type=message_type,
            xml_template_file_path=str(bundle / "template.xml"),
            xsd_schema_file_path=str(bundle / f"{message_type}.xsd"),
            data_file_path=str(csv_file),
            output_path=f"output/{csv_file.stem}.xml",
        )

Always pass ``output_path``: without it the file is written next to the
template and a ``DeprecationWarning`` is raised.

**Can I use Pain001 without templates?**

You do not need to supply one. Every bundled message type ships with a
Jinja2 XML template that the CLI resolves automatically; pass ``-m`` /
``--template`` only to use your own.

Configuration & Templates
=========================

**How do I create a template?**

Templates are Jinja2 XML files that define the structure. Start from a
bundled one (``pain001 inspect <message type>`` shows where it is) and see
:doc:`template_registry`.

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

Run the CLI with ``-v`` / ``--verbose`` for INFO and DEBUG output, and add
``--scheme <profile> --explain`` for a remediation hint per violation:

.. code-block:: bash

    pain001 validate -v -t pain.001.001.03 -d payments.csv --scheme sepa-sct --explain

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
- Process in smaller chunks (``--streaming --chunk-size 1000``)
- Run independent batches in separate processes
- Check system resources (CPU, disk)
- Use SSD for database access

**I get "Memory Error" on large files**

Use streaming, which reads the input in chunks and writes one XML file per
chunk with its own control totals:

.. code-block:: bash

    pain001 generate -t pain.001.001.03 -d large_file.csv -o output --streaming --chunk-size 1000

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

    from pain001 import process_files
    from pain001.constants import TEMPLATES_DIR

    message_type = "pain.001.001.03"
    bundle = TEMPLATES_DIR / message_type

    # SQLite works directly; the file must be under the working directory.
    process_files(
        xml_message_type=message_type,
        xml_template_file_path=str(bundle / "template.xml"),
        xsd_schema_file_path=str(bundle / f"{message_type}.xsd"),
        data_file_path="payments.db",
        output_path="from-db.xml",
    )

**Can I use Pain001 in a web application?**

Yes. Generate in memory with ``generate_xml_string`` so nothing is written
to disk. Do not call ``pain001.main`` from a server: it is the command-line
entry point and exits the process on error.

.. code-block:: python

    import csv
    import io

    from flask import Flask, request

    from pain001 import generate_xml_string
    from pain001.constants import TEMPLATES_DIR

    app = Flask(__name__)
    MESSAGE_TYPE = "pain.001.001.03"
    BUNDLE = TEMPLATES_DIR / MESSAGE_TYPE


    @app.route("/generate-payment", methods=["POST"])
    def generate_payment():
        text = request.files["payments"].read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
        try:
            xml = generate_xml_string(
                rows,
                MESSAGE_TYPE,
                str(BUNDLE / "template.xml"),
                str(BUNDLE / f"{MESSAGE_TYPE}.xsd"),
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400
        return xml, 200, {"Content-Type": "application/xml"}

For a ready-made service, ``pain001 serve`` (``api`` extra) runs the REST API.

Security
========

**Is Pain001 secure for production use?**

Yes! Pain001 implements:
- XXE attack prevention (defusedxml)
- SQL injection protection (parameterised queries)
- Input validation and sanitization
- Secure error messages (no sensitive data)
- Structured JSON logging with PII redaction (``pain001.logging_schema``)

Pain001 has no dedicated audit log; record who generated and sent each file
in your own system.

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

**How do I write pain001's logs to a file?**

Install the JSON formatter on the ``pain001`` logger; IBAN, BIC and name
fields are redacted:

.. code-block:: python

    from pain001.logging_schema import configure_json_logging

    configure_json_logging(log_file="pain001.log", console_output=False)

Getting Help
============

**Where can I get help?**

- `Documentation <https://docs.pain001.com/>`_
- `GitHub Issues <https://github.com/sebastienrousseau/pain001/issues>`_
- Confidential security matters only: see the `security policy
  <https://github.com/sebastienrousseau/pain001/blob/main/SECURITY.md>`_
  (``contact@pain001.com`` is kept for those, not for general help).

**Is there paid support?**

No. Pain001 is free open-source software with no paid tier and no SLA;
the `maintenance policy
<https://github.com/sebastienrousseau/pain001/blob/main/docs/maintenance-policy.md>`_
says what to expect. Its licence lets any firm support it commercially;
the project has no commercial partners and takes no fees or referrals.

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
