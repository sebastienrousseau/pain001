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

   from pathlib import Path

   from pain001.constants import TEMPLATES_DIR
   from pain001.core.core import process_files_streaming

   message_type = "pain.001.001.11"
   bundle = TEMPLATES_DIR / message_type
   Path("output").mkdir(exist_ok=True)
   files = process_files_streaming(
       message_type,
       str(bundle / "template.xml"),
       str(bundle / f"{message_type}.xsd"),
       "payments.csv",
       chunk_size=500,
       output_dir="output",
   )

``output_dir`` must already exist. Without it, the chunk files are written
next to the data file. The data file must be under the current working
directory.

Each chunk file is a message of its own. When a run writes more than
one, chunk ``n`` carries ``GrpHdr/MsgId`` ``<id>-<n>`` and, when the
rows name one, ``PmtInf/PmtInfId`` ``<payment_information_id>-<n>``;
the base is shortened so the whole fits the schemas' 35 characters. A
run that fits one chunk keeps its ids, and its file is identical to the
one the batch path writes. Every chunk's rows get the batch path's
validation, and a refused row stops the run (0.0.81).
