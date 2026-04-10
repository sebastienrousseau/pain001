====================
Performance Playbook
====================

Large File Guidance
===================

- Prefer ``--streaming`` for high-row-count CSV, JSONL, and parquet inputs.
- Start with ``--chunk-size 500`` for low-memory runners and increase to
  ``1000`` or ``2000`` on developer machines.
- Reuse bundled templates through the registry instead of repeatedly resolving
  custom paths.
- Use ``scripts/benchmark_large_batches.py`` to measure the current branch on
  representative data before changing chunk sizes.

CPU And Memory Trade-Offs
=========================

- Smaller chunks reduce peak memory but increase file count.
- Larger chunks reduce file count but increase render and validation time per
  output file.
- Validation dominates for complex schemas, so benchmark end-to-end rather than
  just template rendering.

