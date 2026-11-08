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

CI runs the same tier as two shards in parallel
(``make mutate-shard SHARD=REGISTRY`` and ``SHARD=REST``) and gates their
summed score with ``make mutate-gate``, so the floor applies to the tier
as a whole.

Type Checking
=============

Run mypy locally before pushing:

.. code-block:: bash

   poetry run make type
