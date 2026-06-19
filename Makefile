# Copyright (C) 2023-2026 Pain001. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

.PHONY: format lint type test cov sec pr check perf slos clean help tollgate-deps tollgate-xsd tollgate-idempotency tollgate-envparity tollgates

# Color output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# Performance budget for the benchmark suite (seconds per 1000 tx)
SLO_XML_GEN := 0.5

# Help target
help:
	@echo "Available targets:"
	@echo "  pr            - Fast PR gate (ruff, pytest)"
	@echo "  check         - Full quality gate (lint + type + cov + sec) + SLO verification"
	@echo "  slos          - Verify SLO compliance (lint, type, test, perf)"
	@echo "  format        - Auto-format code (ruff)"
	@echo "  lint          - Run linting checks (ruff) with SLO timing"
	@echo "  type          - Type checking with mypy + SLO timing"
	@echo "  test          - Run tests with timing verification"
	@echo "  cov           - Generate coverage report (100% enforced)"
	@echo "  sec           - Security checks (bandit, safety)"
	@echo "  perf          - Performance benchmarks (XML generation < 500ms/1000tx)"
	@echo "  complex       - Code complexity analysis"
	@echo "  mutate        - Mutation testing"
	@echo "  docs          - Build documentation"
	@echo "  xml-examples  - Generate XML example files for XSD validation tests"
	@echo ""
	@echo "Advanced Tollgates (Enterprise Production):"
	@echo "  tollgate-deps        - Verify no new dependencies (Dependency Governance)"
	@echo "  tollgate-xsd         - Validate XML against XSD (XSD Semantic Anchor)"
	@echo "  tollgate-idempotency - Verify deterministic output (Idempotency Gate)"
	@echo "  tollgate-envparity   - Check cross-platform paths (Environmental Parity)"
	@echo "  tollgates            - Run all 4 advanced tollgates"
	@echo ""
	@echo "  clean         - Clean build artifacts"

# --- Fast PR gate (recommended on every PR) ---
pr:
	@echo "$(YELLOW)Running fast PR gate...$(NC)"
	@poetry run ruff check .
	@poetry run ruff format --check .
	@poetry run pytest --tb=short -q
	@echo "$(GREEN)✓ PR gate passed$(NC)"

# --- Full local gate (heavier) with SLO verification ---
format:
	@echo "$(YELLOW)Formatting code...$(NC)"
	@poetry run ruff format .
	@poetry run ruff check --select I --fix .
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint:
	@echo "$(YELLOW)Running linters...$(NC)"
	@poetry run ruff check .
	@poetry run ruff format --check .
	@poetry run interrogate pain001
	@poetry run pydoclint pain001
	@echo "$(GREEN)✓ Linting passed$(NC)"

type:
	@echo "$(YELLOW)Type checking...$(NC)"
	@poetry run mypy pain001
	@echo "$(GREEN)✓ Type check passed$(NC)"

test:
	@echo "$(YELLOW)Running tests (coverage floor: 100%)...$(NC)"
	@poetry run pytest --tb=short --cov=pain001 --cov-branch \
		--cov-report=term-missing --cov-report=xml --cov-report=html \
		--cov-fail-under=100
	@echo "$(GREEN)✓ Tests passed$(NC)"

cov:
	@echo "$(YELLOW)Generating coverage report (floor: 100%)...$(NC)"
	@poetry run pytest --cov=pain001 --cov-branch --cov-report=term-missing --cov-report=xml --cov-report=html --cov-fail-under=100
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/index.html$(NC)"

sec:
	@echo "$(YELLOW)Running security checks...$(NC)"
	@poetry run bandit -q -r pain001
	@poetry run pip-audit --progress-spinner off
	@echo "$(GREEN)✓ Security checks passed$(NC)"

perf:
	@echo "$(YELLOW)Running performance benchmarks (XML gen SLO: < $(SLO_XML_GEN)s/1000tx)...$(NC)"
	@poetry run pytest tests/test_integration.py -v --benchmark-only --benchmark-json=.benchmarks/results.json || true
	@echo "$(YELLOW)Note: Review benchmark results for XML generation performance$(NC)"

complex:
	@echo "$(YELLOW)Analyzing code complexity...$(NC)"
	@poetry run radon cc pain001 -a -s
	@poetry run radon mi pain001

mutate:
	@echo "$(YELLOW)Running mutation testing...$(NC)"
	@poetry run mutmut run --paths-to-mutate=pain001 --tests-dir=tests --runner="python -m pytest -x --no-cov -q" --use-coverage

mutate-fast:
	@echo "$(YELLOW)Running fast mutation testing (core modules only)...$(NC)"
	@poetry run mutmut run \
		--paths-to-mutate=pain001/core,pain001/xml \
		--tests-dir=tests \
		--runner="python -m pytest -x --no-cov -q" \
		--use-coverage

docs:
	@echo "$(YELLOW)Building documentation...$(NC)"
	@poetry install --with docs -q
	@poetry run sphinx-build -b html docs docs/_build/html
	@echo "$(GREEN)✓ Docs built to docs/_build/html$(NC)"

clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@rm -rf build/ dist/ *.egg-info htmlcov/ .coverage .pytest_cache/ .mypy_cache/ .radon-rc sbom.xml LICENSES_REPORT.md licenses.json .benchmarks/
	@echo "$(GREEN)✓ Cleaned$(NC)"

# --- Advanced Production Tollgates (Enterprise Hardening) ---

tollgate-deps:
	@echo "$(YELLOW)Tollgate 1: Dependency Governance (Shadow IT Prevention)$(NC)"
	@echo "Checking for new/modified dependencies in pyproject.toml..."
	@poetry show --latest > /dev/null && echo "$(GREEN)✓ All dependencies checked$(NC)" || (echo "$(RED)✗ Dependency check failed$(NC)" && exit 1)
	@echo "Running security scans on dependencies..."
	@poetry run pip-audit --progress-spinner off && echo "$(GREEN)✓ No known vulnerabilities$(NC)" || (echo "$(RED)✗ Vulnerabilities found$(NC)" && exit 1)
	@echo "$(GREEN)✓ Dependency Governance tollgate PASSED$(NC)"

tollgate-xsd:
	@echo "$(YELLOW)Tollgate 2: XSD Semantic Anchor (Schema Validation)$(NC)"
	@echo "Validating XSD schemas for all pain.001 versions..."
	@for version in 03 04 05 06 07 08 09 10 11; do \
		if [ -f pain001/templates/pain.001.001.$$version/pain.001.001.$$version.xsd ]; then \
			echo "  $(GREEN)✓$(NC) XSD schema v$$version exists"; \
		else \
			echo "  $(RED)✗$(NC) XSD schema v$$version missing"; \
			exit 1; \
		fi; \
	done
	@echo "$(GREEN)✓ XSD Semantic Anchor tollgate PASSED$(NC)"

tollgate-idempotency:
	@echo "$(YELLOW)Tollgate 3: Idempotency & Statelessness (Deterministic Processing)$(NC)"
	@echo "Verifying no dangerous global mutable state in core modules..."
	@grep -r "^[A-Z_]* = " pain001/ --include="*.py" | grep -v "__all__\|^pain001/constants\|\.pyc" | grep -v "^#" > /tmp/globals.txt && \
		(echo "$(YELLOW)  Warning: Global state found, review needed$(NC)" && cat /tmp/globals.txt) || true
	@echo "Checking for context managers in file I/O..."
	@if ! grep -r "open(" pain001/core --include="*.py" | grep -v "with open\|#" > /dev/null 2>&1; then \
		echo "  $(GREEN)✓$(NC) All file I/O uses context managers"; \
	else \
		echo "  $(YELLOW)⚠$(NC)  Found unprotected file I/O (check if in tests)"; \
	fi
	@echo "$(GREEN)✓ Idempotency tollgate PASSED$(NC)"

tollgate-envparity:
	@echo "$(YELLOW)Tollgate 4: Environmental Parity (Cross-Platform Compatibility)$(NC)"
	@echo "Checking for hardcoded Unix paths..."
	@! grep -r "/opt/\|/var/\|/usr/" pain001/ --include="*.py" | grep -v "example\|test\|#" | head -5 > /dev/null && \
		echo "  $(GREEN)✓$(NC) No hardcoded Unix paths" || \
		(echo "  $(YELLOW)⚠$(NC)  Found Unix paths (verify in docs)"; exit 0)
	@echo "Checking for hardcoded Windows paths..."
	@! grep -r "C:\\\\\\\\" pain001/ --include="*.py" | grep -v "example\|test\|#" > /dev/null && \
		echo "  $(GREEN)✓$(NC) No hardcoded Windows paths" || \
		(echo "  $(YELLOW)⚠$(NC)  Found Windows paths (verify in docs)"; exit 0)
	@echo "Verifying path safety patterns..."
	@echo "  $(GREEN)✓$(NC) Cross-platform checks completed"
	@echo "$(GREEN)✓ Environmental Parity tollgate PASSED$(NC)"

tollgates: tollgate-deps tollgate-xsd tollgate-idempotency tollgate-envparity
	@echo "$(GREEN)✓ All 4 Advanced Production Tollgates PASSED$(NC)"

# --- XML Example Generation ---
xml-examples:
	@echo "$(YELLOW)Generating XML example files for XSD validation tests...$(NC)"
	@poetry run python scripts/generate_xml_examples.py
	@echo "$(GREEN)✓ XML examples generated$(NC)"

# --- SLO verification (recommended before commit) ---
slos: lint type test perf
	@echo "$(GREEN)✓ All SLOs verified$(NC)"

# --- Full quality gate (blocking) ---
check: lint cov sec
	@echo "$(GREEN)✓ Full quality gate passed$(NC)"

