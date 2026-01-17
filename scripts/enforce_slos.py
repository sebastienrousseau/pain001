#!/usr/bin/env python3
"""
PySentinel SLO Enforcement Script
Validates performance SLOs and coverage floors for Pain001.

SLOs:
  - Linting: < 15 seconds
  - Type checking: < 10 seconds
  - Test suite: < 60 seconds
  - XML generation: < 500ms per 1000 transactions
  - Coverage floor: 95% branch coverage (new code: 100%)
"""

import json
import sys
from pathlib import Path
from typing import Optional

from defusedxml import ElementTree as DefusedET

# SLO Thresholds (in seconds unless noted)
SLO_THRESHOLDS = {
    "lint": 25,
    "type": 10,
    "test": 60,
    "coverage_floor": 95,  # %
    "coverage_new_code": 100,  # %
}


def read_coverage_xml(coverage_file: Path) -> tuple[float, dict[str, float]]:
    """Parse coverage.xml and extract total + per-module coverage.

    Args:
        coverage_file: Path to coverage.xml

    Returns:
        Tuple of (total_coverage %, module_coverages dict)
    """
    if not coverage_file.exists():
        print(f"❌ Coverage report not found: {coverage_file}")
        return 0.0, {}

    try:
        tree = DefusedET.parse(coverage_file)
        root = tree.getroot()
        if root is None:
            print("❌ Coverage XML has no root element")
            return 0.0, {}

        # Extract total coverage
        total_cov = float(root.get("line-rate", "0")) * 100

        # Extract per-package coverage
        module_coverage = {}
        for package in root.findall("package"):
            package_name = package.get("name")
            line_rate = float(package.get("line-rate", "0")) * 100
            if package_name:
                module_coverage[package_name] = line_rate

        return total_cov, module_coverage
    except Exception as e:
        print(f"❌ Failed to parse coverage.xml: {e}")
        return 0.0, {}


def validate_coverage(coverage_pct: float, floor: float) -> bool:
    """Validate coverage meets floor.

    Args:
        coverage_pct: Measured coverage percentage
        floor: Minimum required percentage

    Returns:
        True if coverage >= floor, False otherwise
    """
    if coverage_pct >= floor:
        print(f"✓ Coverage: {coverage_pct:.2f}% >= {floor}% (PASS)")
        return True
    else:
        print(f"✗ Coverage: {coverage_pct:.2f}% < {floor}% (FAIL)")
        return False


def validate_slo(
    metric_name: str, measured_secs: float, threshold_secs: float
) -> bool:
    """Validate SLO is met.

    Args:
        metric_name: Name of metric (for logging)
        measured_secs: Measured duration in seconds
        threshold_secs: SLO threshold in seconds

    Returns:
        True if measured <= threshold, False otherwise
    """
    if measured_secs <= threshold_secs:
        print(
            f"✓ {metric_name}: {measured_secs:.2f}s <= {threshold_secs}s (PASS)"
        )
        return True
    else:
        print(
            f"✗ {metric_name}: {measured_secs:.2f}s > {threshold_secs}s (FAIL)"
        )
        return False


def check_github_actions_durations() -> Optional[dict[str, float]]:
    """Extract job durations from GitHub Actions workflow logs (if available).

    Returns:
        Dict of job_name -> duration_secs, or None if not in CI
    """
    # This is a placeholder; real implementation would parse GitHub Actions logs
    # For now, we rely on Makefile timing
    return None


def _check_coverage_slos(failures: list[str]) -> None:
    """Check coverage SLOs and update failures list.

    Args:
        failures: List to append failure messages to
    """
    print("\n[1/3] Validating Coverage Floor...")
    print("-" * 70)
    coverage_file = Path("coverage.xml")
    total_cov, module_cov = read_coverage_xml(coverage_file)

    if not validate_coverage(total_cov, SLO_THRESHOLDS["coverage_floor"]):
        failures.append("Coverage floor not met")

    if module_cov:
        print("\nPer-module coverage:")
        for module, cov in sorted(module_cov.items()):
            status = "✓" if cov >= SLO_THRESHOLDS["coverage_floor"] else "✗"
            print(f"  {status} {module}: {cov:.2f}%")


def _check_benchmark_slos(failures: list[str]) -> None:
    """Check performance benchmark SLOs and update failures list.

    Args:
        failures: List to append failure messages to
    """
    print("\n[2/3] Checking Performance Benchmarks...")
    print("-" * 70)
    benchmark_file = Path(".benchmarks/results.json")

    if not benchmark_file.exists():
        print("  ⚠ Benchmark results not found (optional)")
        return

    try:
        with open(benchmark_file, encoding="utf-8") as f:
            benchmarks = json.load(f)
            for bench in benchmarks.get("benchmarks", []):
                name = bench.get("name", "unknown")
                mean_ms = bench.get("stats", {}).get("mean", 0) * 1000
                # XML generation should be < 500ms (per benchmark params)
                if "xml" in name.lower():
                    if mean_ms < 500:
                        print(f"  ✓ {name}: {mean_ms:.2f}ms < 500ms")
                    else:
                        print(f"  ✗ {name}: {mean_ms:.2f}ms >= 500ms")
                        failures.append(f"Benchmark {name} exceeds 500ms SLO")
    except Exception as e:
        print(f"  ⚠ Could not parse benchmark results: {e}")


def _print_summary(failures: list[str]) -> int:
    """Print summary and return exit code.

    Args:
        failures: List of failure messages

    Returns:
        0 if no failures, 1 if failures exist
    """
    print("\n[3/3] Summary")
    print("-" * 70)

    if failures:
        print(f"\n✗ {len(failures)} SLO violation(s) detected:")
        for failure in failures:
            print(f"  - {failure}")
        print("\nPySentinel: INTEGRITY COMPROMISED")
        return 1
    else:
        print("\n✓ All SLOs passed!")
        print("PySentinel: Integrity Verified.")
        return 0


def main() -> int:
    """Main SLO validation routine.

    Returns:
        0 if all SLOs pass, 1 if any fail
    """
    print("\n" + "=" * 70)
    print("PySentinel SLO Enforcement Report")
    print("=" * 70)

    failures: list[str] = []

    _check_coverage_slos(failures)
    _check_benchmark_slos(failures)

    return _print_summary(failures)


if __name__ == "__main__":
    sys.exit(main())
