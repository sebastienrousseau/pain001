Version Migration
=================

Pain001 includes a migration utility for upgrading legacy payment data to
modern ISO 20022 pain.001 variants.

Command line usage:

.. code-block:: bash

   python -m pain001.migrate --from v03 --to v09 --source payments.csv
   python -m pain001.migrate --from v05 --to v11 --source payments.csv --output migrated.csv

The migration command:

* Loads the source payment rows.
* Applies a version mapping to the target field set.
* Validates the migrated rows by rendering target-version XML against the bundled XSD.
* Writes migrated CSV output next to the source file by default.

Supported migration paths in this branch:

* Legacy pain.001.001.03-.08 to modern pain.001.001.09-.11
* Explicit YAML mapping assets for ``v03 -> v09`` and ``v05 -> v11``

