===============
Testing Quality
===============

Property-Based Tests
====================

Pain001 uses Hypothesis to fuzz:

- IBAN validation
- BIC validation
- payment row validation

Mutation Testing
================

Use ``mutmut`` with the repository ``mutmut.ini`` to focus on critical paths:

.. code-block:: bash

   poetry run mutmut run

Type Checking
=============

Run mypy locally before pushing:

.. code-block:: bash

   poetry run mypy pain001 tests

