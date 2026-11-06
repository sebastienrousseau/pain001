Additional Message Types
========================

Pain001 now includes incremental support for more ISO 20022 families beyond
``pain.001``:

``pain.008.001.02`` and ``pain.008.001.08``
    Direct debit initiation generation is supported through the same XML
    generation pipeline used for ``pain.001``. V02 is the version legacy
    SEPA files carry; V08 is the one the EPC 2025 Direct Debit rulebooks
    and CBPR+ specify. Both take the same 26-column CSV; the rendered
    difference is ``BICFI`` in place of ``BIC``.

    The columns name the direct-debit roles. The ``creditor_*`` columns
    (``creditor_name``, ``creditor_account_IBAN``, ``creditor_agent_BIC``)
    describe the party that collects, once per batch, and fill ``Cdtr``,
    ``CdtrAcct`` and ``CdtrAgt``; the batch takes them from the first row.
    The ``debtor_*`` columns describe the party that pays, row by row, and
    fill each transaction's ``Dbtr``, ``DbtrAcct`` and ``DbtrAgt``. This is
    the reverse of ``pain.001``, where the debtor sends the batch.

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

