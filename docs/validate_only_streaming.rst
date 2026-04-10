===========================
Validate-Only And Streaming
===========================

Validate-Only
=============

Use ``--dry-run`` or ``--validate-only`` to validate template, schema, and
payment data without writing XML files:

.. code-block:: bash

   pain001 -t pain.001.001.11 -d payments.csv --dry-run

Streaming
=========

Use chunked generation for large files:

.. code-block:: bash

   pain001 -t pain.001.001.11 -d payments.csv --streaming --chunk-size 500

Library usage:

.. code-block:: python

   from pain001.core.core import process_files_streaming

   files = process_files_streaming(
       "pain.001.001.11",
       "pain001/templates/pain.001.001.11/template.xml",
       "pain001/templates/pain.001.001.11/pain.001.001.11.xsd",
       "payments.csv",
       chunk_size=500,
   )

