.. SPDX-License-Identifier: Apache-2.0 OR MIT

========
Examples
========

These examples use synthetic data and the bundled templates. Their source
is included directly from scripts executed by ``tests/test_examples.py``;
the manual does not maintain a second, untested copy of each program.
Run them from the repository root after
``poetry install --all-extras --with dev``.

See :doc:`verification-coverage` for the feature-to-test evidence map and
its limits. Passing an example does not certify a payment for a bank.

Example 1: Basic SEPA Payment Processing
========================================

Load the bundled CSV, render XML, validate against the XSD and write to an
explicit temporary output path. Scheme approval is a separate validation
step; an ISO message edition alone does not identify a payment rail.

.. literalinclude:: ../examples/01_generate_xml_file.py
   :language: python
   :start-at: import tempfile

Example 2: Batch Payment Processing from CSV
============================================

Use the streaming workflow below for bounded chunks, or invoke the library
once per input with a distinct explicit ``output_path``. A calculated filename
does not control output unless it is passed to the generation API. Never mark
an input successful merely because an exception was caught.

.. literalinclude:: ../examples/09_streaming_large_batch.py
   :language: python
   :start-at: import tempfile

Example 3: Database-Driven Payment Processing
=============================================

The SQLite loader reads the configured payment table. Executing a separate
SQL query does not pass that query's result to the loader. For a filtered
pipeline, pass the selected, normalized records to ``generate_xml_string``;
test that selection separately. File generation is not bank acceptance and
must not by itself mark all pending ledger records as processed.

The runnable format example compares CSV, JSON, JSON Lines and Parquet rows
and demonstrates reading the bundled SQLite database:

.. literalinclude:: ../examples/10_input_formats.py
   :language: python
   :start-at: import json

Example 4: Multi-Version Support
================================

Discover supported editions with ``pain001 versions``. Choose the edition
and scheme required by the recipient; labels such as "instant" must not be
invented from an edition number. The regression matrix generates every
discovered bundled message type. This example demonstrates version mapping:

.. literalinclude:: ../examples/08_version_migration.py
   :language: python
   :start-at: import tempfile

Example 5: Error Handling and Logging
=====================================

The CLI example asserts success and failure exit codes. Logs and metrics
must not contain real account records or secrets. Use the actual exception
types documented in :mod:`pain001.exceptions`, not hypothetical exception
names or attributes. This executable metrics example shows application hooks:

.. literalinclude:: ../examples/11_observability_metrics.py
   :language: python
   :start-at: import tempfile

Example 6: Large Batch Processing with Chunking
===============================================

Use ``process_files_streaming`` as demonstrated in Example 2. It preserves
record order and produces one validated output per chunk. Keep identifiers
as strings; generic dataframe type inference can destroy leading zeros.
The generation benchmark verifies output transaction and chunk counts in
addition to reporting memory and time. See :doc:`BENCHMARKS`.

Example 7: Payment Amount Validation
====================================

Validate monetary values using exact decimal rules, not binary floating-point
comparisons or an invented ``Amount`` column. The policy example verifies the
limit boundary, warning behavior, request isolation and fail-closed handling
of missing inputs. Matching predicates produce findings; they do not modify
payment amounts. Schema and recipient-specific checks still apply.

.. literalinclude:: ../examples/17_custom_policies.py
   :language: python
   :start-at: from copy

Example 8: Custom Data Processing Pipeline
==========================================

A plugin participates in the same eager and streaming dispatch as built-ins.
This example proves that registration affects execution and preserves every
row. It uses an example-only extension and no installed distribution changes.
Production packaging and the pre-1.0 contract are documented in :doc:`plugins`.

.. literalinclude:: ../examples/19_plugin_dispatch.py
   :language: python
   :start-at: from collections

See Also
========

- :doc:`installation`
- :doc:`usage`
- :doc:`configuration`
- :doc:`modules`
- :doc:`verification-coverage`
