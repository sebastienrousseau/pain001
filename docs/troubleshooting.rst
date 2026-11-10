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

- Cause: missing required CSV columns, invalid IBAN/BIC fields, or bad dates.
- Fix: run ``pain001 validate -t <message type> -d <data file>`` first and
  inspect the validation error; add ``--scheme <profile>`` for IBAN check
  digits, currency and amount rules.

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

