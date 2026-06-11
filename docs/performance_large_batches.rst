Large-Batch Performance
=======================

Pain001 now ships with a concrete large-batch benchmark workflow and a
streaming generation mode for chunked processing.

Recommended approach for large input files:

* Use ``--streaming`` with an explicit ``--chunk-size`` to keep memory bounded.
* Benchmark your actual data shape before increasing chunk size.
* Prefer chunk sizes in the ``500`` to ``5000`` range unless profiling shows otherwise.

Example:

.. code-block:: bash

   pain001 -t pain.001.001.03 -m template.xml -s schema.xsd -d payments.csv --streaming --chunk-size 1000
   poetry run python scripts/benchmark_large_batches.py

What to measure:

* Total rows processed
* Wall-clock generation time
* Per-chunk generation time
* Number of XML files emitted in streaming mode

