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

Every load checks each IBAN (length for its country and mod-97 check digits)
and BIC (ISO 9362) column, whatever the scheme. A failure names the row
(counted from 0) and the column, never the identifier. ``--no-identifier-checks``
on ``generate`` and ``validate``, ``identifier_checks=False`` in
``process_files``, ``process_files_streaming``, ``load_payment_data`` and
their async forms, and ``"identifier_checks": false`` in a ``POST /api/validate``,
``/api/generate`` or ``/api/generate/async`` body turn the checks off; keep
them on for anything a bank will see.

Generation recomputes control totals and validates rendered XML against the
bundled XSD before writing. Scheme validation, including anti-duplicate,
adds domain rules but does not certify compliance with a bank's private rules.
Streaming creates one output per chunk.

Checking existing files
=======================

``pain001 check`` runs the validation ladder on pain.001 and pain.008
files that already exist, whoever wrote them: the bundled XSD of the
message type the file's namespace names, then the message definition's
cross-element rules. ``--scheme`` adds scheme profiles (comma-separated),
``--rules`` a private CEL policy (``pain001[rules]``) and ``--schematron``
a rulebook, each run on the file as it stands.

.. code-block:: bash

   pain001 check out/*.xml
   pain001 check --scheme sepa-sct --format json out/batch.xml
   pain001 check --format sarif -o check.sarif out/*.xml

It exits 0 when every file passes, 1 when any file has an error finding,
and 2 when a file is not a bundled pain.001 or pain.008 message, is not
UTF-8, is over 10 MiB, carries a DTD, or an option names an unknown
scheme or rulebook. Every file gets a report; ``--format sarif`` writes
one SARIF 2.1.0 log for code scanning. In Python, ``check_document``
returns the same report:

.. code-block:: python

   from pain001 import check_document

   report = check_document(xml_text, scheme="sepa-sct")
   for finding in report.findings:
       print(finding.rung, finding.rule, finding.location, finding.message)

Python: in-memory output
========================

Data files must be under the current working directory; a path outside it
is refused with ``SecurityError``. This example copies the synthetic sample
shipped in the installed package into the working directory first, and uses
the bundled template and schema in place:

.. code-block:: python

   import shutil

   from pain001 import generate_xml_string
   from pain001.constants import TEMPLATES_DIR
   from pain001.csv.load_csv_data import load_csv_data

   message_type = "pain.001.001.03"
   bundle = TEMPLATES_DIR / message_type
   shutil.copy(bundle / "template.csv", "payments.csv")
   rows = load_csv_data("payments.csv")
   xml = generate_xml_string(
       rows,
       message_type,
       str(bundle / "template.xml"),
       str(bundle / f"{message_type}.xsd"),
   )

Python: explicit file output
============================

.. code-block:: python

   import shutil

   from pain001 import process_files
   from pain001.constants import TEMPLATES_DIR

   message_type = "pain.001.001.03"
   bundle = TEMPLATES_DIR / message_type
   shutil.copy(bundle / "template.csv", "payments.csv")
   output = process_files(
       xml_message_type=message_type,
       xml_template_file_path=str(bundle / "template.xml"),
       xsd_schema_file_path=str(bundle / f"{message_type}.xsd"),
       data_file_path="payments.csv",
       output_path="payment.xml",
   )

Unlike the CLI directory flag, the Python output_path argument names a file.
Always provide it so an installed template directory is not used as output.

Optional integrations
=====================

REST is started with pain001 serve after installing the api extra.
:doc:`custom-rules` apply through CLI and REST (``rules`` extra), MCP offers
review-only record corrections (``mcp`` extra), and :doc:`sftp-upload`
delivers a file explicitly (``upload`` extra). Generation never uploads a
payment automatically.
