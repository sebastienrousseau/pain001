.. SPDX-License-Identifier: Apache-2.0 OR MIT

=============
Using Pain001
=============

CLI workflow
============

Run this in a fresh writable directory using synthetic bundled data:

.. code-block:: bash

   pain001 init pain.001.001.03 -o payments.csv
   pain001 validate -t pain.001.001.03 -d payments.csv
   pain001 generate -t pain.001.001.03 -d payments.csv -o output

The generate command's -o flag names an output directory. Template and schema
paths resolve from the bundled registry unless explicitly overridden.
Exit codes are 0 for success, 1 for processing/validation failure, and 2 for
invalid arguments or configuration. Dry-run validates data without writing
XML; it is not a bank-acceptance guarantee.

Use generated help rather than a duplicate flag table:

.. code-block:: bash

   pain001 generate --help
   pain001 versions
   pain001 inspect pain.001.001.03

Inputs and validation
=====================

CSV, SQLite, JSON and JSONL are supported, as are Python records and optional
Parquet input. Installed plugins can add formats such as XLSX. See
:doc:`plugins` for privileges, discovery and disable controls, and
:doc:`input-columns` for schema-derived field mappings.

Generation recomputes control totals and validates rendered XML against the
bundled XSD before writing. Scheme validation, including anti-duplicate,
adds domain rules but does not certify compliance with a bank's private rules.
Streaming creates one output per chunk.

Python: in-memory output
========================

This example reads synthetic data shipped in the installed package:

.. code-block:: python

   from pain001 import generate_xml_string
   from pain001.constants import TEMPLATES_DIR
   from pain001.csv.load_csv_data import load_csv_data

   message_type = "pain.001.001.03"
   bundle = TEMPLATES_DIR / message_type
   rows = load_csv_data(str(bundle / "template.csv"))
   xml = generate_xml_string(
       rows,
       message_type,
       str(bundle / "template.xml"),
       str(bundle / f"{message_type}.xsd"),
   )

Python: explicit file output
============================

.. code-block:: python

   from pain001.core.core import process_files
   from pain001.constants import TEMPLATES_DIR

   message_type = "pain.001.001.03"
   bundle = TEMPLATES_DIR / message_type
   output = process_files(
       xml_message_type=message_type,
       xml_template_file_path=str(bundle / "template.xml"),
       xsd_schema_file_path=str(bundle / f"{message_type}.xsd"),
       data_file_path=str(bundle / "template.csv"),
       output_path="payment.xml",
   )

Unlike the CLI directory flag, the Python output_path argument names a file.
Always provide it so an installed template directory is not used as output.

Optional and unreleased integrations
====================================

REST is started with pain001 serve after installing the api extra.
The feature branch also supports :doc:`custom-rules` through CLI and REST,
review-only MCP corrections, and explicit :doc:`sftp-upload`. Generation
never uploads a payment automatically. See :doc:`issue-audit` for branch
availability, companion work and unmet acceptance criteria.
