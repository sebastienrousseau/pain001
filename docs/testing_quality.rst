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

Use mutmut 3 with ``[tool.mutmut]`` in ``pyproject.toml``:

.. code-block:: bash

   poetry run make mutate-fast

Type Checking
=============

Run mypy locally before pushing:

.. code-block:: bash

   poetry run make type
