# Python Performance Tollgate

## Mission

Enforce SLO compliance and prevent performance regressions in payment processing.

## Tollgate Objectives

- Enforce **XML generation < 500ms** for 1000 transactions
- Enforce **test suite < 60s** execution time
- Enforce **no memory leaks** in long-running operations
- Detect **performance regressions** > 10% slowdown

## When This Tollgate Applies

- Modifying `pain001/core/core.py` (orchestration)
- Modifying `pain001/xml/generate_xml.py` (XML generation)
- Modifying `pain001/data/loader.py` (data loading)
- Adding new features that process large datasets

## Tollgate Checks

### 1. Benchmark XML Generation (MANDATORY)

```bash
# Run performance benchmark
poetry run pytest tests/test_performance.py --benchmark-only

# Expected output:
# test_xml_generation_1000_transactions: < 500ms (mean)
# test_csv_loading_10000_rows: < 200ms (mean)
# test_db_loading_10000_rows: < 150ms (mean)
```

**Success Criteria:**

- XML generation: < 500ms for 1000 transactions
- CSV loading: < 200ms for 10,000 rows
- SQLite loading: < 150ms for 10,000 rows
- No regression > 10% from baseline

### 2. Memory Profiling (For Large Dataset Changes)

```bash
# Profile memory usage
poetry run python -m memory_profiler scripts/profile_memory.py

# Check for leaks:
grep -i "leak\|growing\|increase" memory_profile.log
```

**Success Criteria:**

- Peak memory < 500MB for 10,000 transactions
- No memory growth in repeated runs
- Proper cleanup of file handles and connections

### 3. Test Suite Performance (MANDATORY)

```bash
# Time full test suite
time poetry run pytest

# Must complete in < 60s
```

**Success Criteria:**

- Total test time: < 60 seconds
- Individual test: < 5 seconds (except integration tests)
- No tests marked `slow` without justification

### 4. Cyclomatic Complexity (Code Maintainability)

```bash
# Check complexity scores
poetry run radon cc pain001/ -a -nb

# Flag functions with complexity > 10
poetry run radon cc pain001/ -n C
```

**Success Criteria:**

- Average complexity: < 5 (A grade)
- No functions > 15 complexity (refuse D/F grades)
- Refactor complex functions into smaller units

### 5. Load Testing (For Major Changes)

```bash
# Stress test with large dataset
poetry run python scripts/stress_test.py --transactions 50000

# Verify:
# - No crashes
# - Linear time complexity O(n)
# - Memory stays bounded
```

**Success Criteria:**

- 50,000 transactions: < 20 seconds
- Memory usage: < 2GB
- No exceptions or timeouts

## Red Lines (NEVER Violate)

- ❌ NEVER merge code that increases XML generation time > 10%
- ❌ NEVER add O(n²) or worse algorithms without justification
- ❌ NEVER skip benchmarks for core performance paths
- ❌ NEVER ignore memory leaks (even small ones compound)
- ❌ NEVER commit code with complexity > 15 (refactor first)

## Performance Budget

| Operation | Budget | Current | Headroom |
|-----------|--------|---------|----------|
| XML gen (1k tx) | 500ms | ~350ms | 150ms |
| CSV load (10k rows) | 200ms | ~120ms | 80ms |
| DB load (10k rows) | 150ms | ~80ms | 70ms |
| Test suite | 60s | ~44s | 16s |
| Type check | 10s | ~2s | 8s |
| Linting | 15s | ~11s | 4s |

## Benchmark Baseline Files

Create baseline benchmarks for comparison:

```bash
# Generate baseline (do this once after release)
poetry run pytest tests/test_performance.py --benchmark-only \
  --benchmark-save=baseline_v0.0.44

# Compare against baseline (do this in PRs)
poetry run pytest tests/test_performance.py --benchmark-only \
  --benchmark-compare=baseline_v0.0.44
```

## Performance Test Template

```python
# tests/test_performance.py
import pytest
from pain001.core.core import process_files

@pytest.mark.benchmark(group="xml-generation")
def test_xml_generation_1000_transactions(benchmark, tmp_path):
    """Benchmark XML generation for 1000 transactions."""
    # Setup
    csv_path = "tests/fixtures/perf_1000_transactions.csv"
    output = tmp_path / "output.xml"
    
    # Benchmark
    result = benchmark(
        process_files,
        xml_message_type="pain.001.001.03",
        data_path=str(csv_path),
        output_file_path=str(output)
    )
    
    # Assert performance budget
    assert benchmark.stats.mean < 0.5  # 500ms
    assert result is not None

@pytest.mark.benchmark(group="data-loading")
def test_csv_loading_10000_rows(benchmark):
    """Benchmark CSV loading for 10,000 rows."""
    from pain001.csv.load_csv_data import load_csv_data
    
    csv_path = "tests/fixtures/perf_10000_rows.csv"
    result = benchmark(load_csv_data, csv_path)
    
    assert benchmark.stats.mean < 0.2  # 200ms
    assert len(result) == 10000
```

## Escalation Path

If performance degrades:

1. **STOP** - Do not merge PR
2. **Profile** - Use `cProfile` or `memory_profiler` to find hotspot
3. **Optimize** - Refactor slow code
4. **Verify** - Re-run benchmark, confirm improvement
5. **Document** - Add comment explaining optimization

## Integration with CI/CD

Add to `.github/workflows/quality.yml`:

```yaml
- name: Run Performance Benchmarks
  run: |
    poetry run pytest tests/test_performance.py --benchmark-only \
      --benchmark-compare=baseline_v0.0.44 \
      --benchmark-compare-fail=mean:10%
```

This fails CI if performance regresses > 10%.

## Why This Matters

- **User Experience**: Slow payment processing = unhappy users
- **Scalability**: Performance issues compound at scale (1k → 100k transactions)
- **Cost**: Slower processing = higher infrastructure costs
- **Reliability**: Performance bugs often indicate deeper issues

## Success Metrics

- Zero performance regressions merged to main
- All benchmarks consistently green
- Performance budget headroom maintained
- No production performance incidents
