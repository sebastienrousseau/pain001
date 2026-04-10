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
- Fix: run ``pain001 --dry-run`` first and inspect the validation error.

Path validation failed
----------------------

- Cause: parent traversal, output path outside the working directory, or
  unsupported template directives.
- Fix: use repo-local or temp-local paths, and avoid Jinja ``include``,
  ``extends``, and ``import`` directives in XML templates.

CLI Exit Codes
==============

- ``0``: success
- ``1``: validation or processing failure
- ``2``: CLI/configuration error

