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
Exit codes are 0 for success, 1 for findings (processing or validation
failure), 2 for invalid arguments, a missing input file or configuration,
and 3 for a bank rejection read by ``pain001 status``
(:doc:`troubleshooting` has the table). Dry-run validates data without writing
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

Every load checks each IBAN (length for its country and mod-97 check digits),
BIC (ISO 9362) and LEI (``*_lei``: ISO 17442 check digits) column, whatever
the scheme. A failure names the row
(counted from 0) and the column, never the identifier. ``--no-identifier-checks``
on ``generate`` and ``validate``, ``identifier_checks=False`` in
``process_files``, ``process_files_streaming``, ``load_payment_data`` and
their async forms, and ``"identifier_checks": false`` in a ``POST /api/validate``,
``/api/generate`` or ``/api/generate/async`` body turn the checks off; keep
them on for anything a bank will see.

Generation recomputes control totals and validates rendered XML against the
bundled XSD before writing. Scheme validation, including anti-duplicate,
adds domain rules but does not certify compliance with a bank's private rules.
Streaming creates one output per chunk. ``--workers N`` (with
``--streaming``; ``workers=N`` in ``process_files_streaming``, or
``PAIN001_WORKERS``) builds
chunks in N processes and writes the same files in the same order: four
workers took 40,000 rows from 1.6 s to 0.9 s on a six-core machine. A
chunk that fails leaves the chunks before it and nothing after it. From
Python, call it under ``if __name__ == "__main__":``, as with any
``multiprocessing`` code, because the workers start fresh interpreters.

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

Over REST (``pain001 serve``), ``POST /api/v1/check`` takes the document
as XML text in a JSON body with optional ``scheme`` and ``schematron``
fields, and answers the same report. A Schematron rulebook is named by
preset only (``sepa``, ``fednow``, ``cbpr``), never a server path. A
failed rung is a ``200`` with ``"passed": false``; a document that
cannot be checked is a ``422``.

Signing and verifying signatures
================================

``--xml-sign-key`` on ``generate`` adds an enveloped W3C XML-DSig
signature (``pain001[sign]``). The algorithm follows the key: an RSA key
signs ``rsa-sha256``, a P-256 or P-384 key ``ecdsa-sha256`` or
``ecdsa-sha384``. ``--xml-sign-alg rsa-pss-sha256`` signs RSA-PSS
instead. ``--xml-sign-cert`` embeds the signer's certificate.

``pain001 verify-signature`` checks the signature on files you received
or wrote. Pass the signer's certificate (or public key) with ``--cert``;
that is the trust anchor. ``--trust-embedded-cert`` verifies with each
file's own certificate instead, which proves the file is unchanged since
it was signed but not who signed it, since anyone can sign with a
certificate they made.

.. code-block:: bash

   pain001 verify-signature out/batch.xml --cert bank-signer.pem
   pain001 verify-signature out/*.xml --cert ours.pem --format json

It exits 0 when every file verifies, 1 when any does not, and 2 when it
cannot run (no trust choice, an unreadable certificate). In Python,
``verify_signature`` returns a ``SignatureReport``:

.. code-block:: python

   from pain001 import verify_signature

   report = verify_signature(signed_xml, trust_anchor=cert_pem)
   print(report.valid, report.algorithm, report.signer, report.reason)

Verification uses exclusive C14N 1.0 on the parsed document and accepts
only the algorithms above, SHA-256 to SHA-512 digests, and a reference
to the whole document with the enveloped transform. The certificate's
chain and validity dates are not checked. ``verify_xml_signature``
requires an explicit ``public_key_pem`` or ``cert_pem``; a call without
one raises ``ValueError``. For an explicit integrity-only check, use
``verify_signature(..., trust_embedded_cert=True)``. This change was
announced in 0.0.83 (ADR-0012).

Signing also uses exclusive C14N 1.0 on the parsed tree and preserves the
input's namespace prefixes. For a head.001.001.03 Business Application
Header, the signature is inside ``AppHdr/Sgntr``; without that header it
is an enveloped signature on the document root. The whole document is
covered in both cases, including the header and payment payload.

In CI
-----

The repository is also a GitHub Action. It installs pain001 from the
tag you pin, checks the files, uploads the findings to code scanning
and fails the job when a file does not pass. ``--skip-other-xml`` is
on, so a glob may match XML that is not a payment:

.. code-block:: yaml

   permissions:
     contents: read
     security-events: write   # for the SARIF upload
   steps:
     - uses: actions/checkout@<sha>
     - uses: sebastienrousseau/pain001@v0.0.86
       with:
         files: "payments/**/*.xml"
         scheme: sepa-sct

``files`` takes paths or globs (``**`` recurses); ``schematron``,
``rules``, ``sarif-file``, ``upload-sarif: "false"`` and
``python-version`` are optional.

For pre-commit, ``pain001-check`` checks staged XML files and
``pain001-validate`` validates a data file when it changes:

.. code-block:: yaml

   - repo: https://github.com/sebastienrousseau/pain001
     rev: v0.0.82
     hooks:
       - id: pain001-check
       - id: pain001-validate
         args: [-t, pain.001.001.09, -d, payments.csv]
         files: ^payments\.csv$

Python: in-memory output
========================

From Python, data files must be under the current working directory; a
path outside it is refused with ``SecurityError``. The command line reads
the files you name on it wherever they are. This example copies the synthetic sample
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
delivers a file explicitly and collects the bank's replies with
``pain001 download`` (``upload`` extra). ``pain001 status`` reads those
replies and exits 3 on any rejection. Generation never uploads a payment
automatically.
