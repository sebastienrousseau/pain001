Additional Message Types
========================

Pain001 now includes incremental support for more ISO 20022 families beyond
``pain.001``:

``pain.008.001.02``
    Direct debit initiation generation is supported through the same XML
    generation pipeline used for ``pain.001``.

``pain.002``
    Payment status reports can be parsed into Python dictionaries with
    ``pain001.pain002.parse_pain002_report``.

``camt.053``
    Bank statements can be parsed into Python dictionaries with
    ``pain001.camt053.parse_camt053_statement``.

Examples:

.. code-block:: python

   from pain001.pain002 import parse_pain002_report
   from pain001.camt053 import parse_camt053_statement

   pain002 = parse_pain002_report("pain001/test_fixtures/pain002_sample.xml")
   statement = parse_camt053_statement("pain001/test_fixtures/camt053_sample.xml")

