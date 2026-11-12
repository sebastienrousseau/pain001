===============
Troubleshooting
===============

Common Failures
===============

Schema validation failed
------------------------

- Cause: template and XSD versions do not match.
- Fix: use the same message type for both assets, or omit ``--template`` and
  ``--schema`` so the registry auto-resolves bundled files.

Data validation failed
----------------------

- Cause: missing required CSV columns, invalid IBAN/BIC/LEI fields, or bad dates.
- Fix: run ``pain001 validate -t <message type> -d <data file>`` first.
  Each problem is listed on its own line with the line number as a
  spreadsheet shows it (a CSV header is line 1), the column and a
  stable code; the first 20 are shown, then a count. The value itself
  is never printed. Add ``--scheme <profile>`` for currency and amount
  rules.

  ================  ===============================================
  Code              Problem
  ================  ===============================================
  ``P001-E001``     The input has no payment rows.
  ``P001-E002``     A CSV row has more values than the header has
                    columns (a stray comma or an unquoted value).
  ``P001-E010``     A required column is absent or empty.
  ``P001-E011``     Not a whole number.
  ``P001-E012``     Not a decimal number (an amount).
  ``P001-E013``     Not true, false, 1 or 0.
  ``P001-E014``     Not a date (``YYYY-MM-DD`` or ISO 8601).
  ``P001-E020``     Not a valid IBAN.
  ``P001-E021``     Not a valid BIC.
  ``P001-E022``     Not a valid LEI (ISO 17442 check digits).
  ``P001-E030``     Breaks the message type's JSON Schema (for
                    example ``currency=EURO``: not three letters).
  ``P001-E040``     Breaks a rule of the scheme or policy asked for
                    (``pain001.generate(..., scheme=...)``).
  ================  ===============================================

  From Python, the same problems are on the exception:
  ``PaymentValidationError.errors`` is a tuple of ``RowIssue`` records
  (``line``, ``column``, ``code``, ``message``).

Input file not found
--------------------

- Cause: a ``-d``, ``-m`` or ``-s`` path that does not exist. The command
  exits 2 before it prints progress or creates the output directory.
- Fix: check the path. The command line reads files you name on it from
  any directory.

Path validation failed
----------------------

- Cause: from Python, the REST API or the MCP server, a data, template
  or schema path outside the working directory (or the temporary
  directory), parent traversal, or unsupported template directives. The
  output path is not restricted.
- Fix: keep inputs under the working directory for those callers, and
  avoid Jinja ``include``, ``extends``, and ``import`` directives in XML
  templates.

CLI Exit Codes
==============

Every ``pain001`` command uses the same codes:

.. list-table::
   :header-rows: 1

   * - Code
     - Meaning
   * - ``0``
     - Success.
   * - ``1``
     - Findings: the data, the file or a rulebook check failed, or
       generation failed.
   * - ``2``
     - Usage, input/output or configuration error: a bad option, a
       missing input file, an invalid environment value such as
       ``PAIN001_CHUNK_SIZE=abc`` (the message names the variable), or
       a file ``check`` cannot read.
   * - ``3``
     - The bank rejected the payment (``pain001 status`` read a
       rejection from a status report).

