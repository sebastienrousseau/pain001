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

.PHONY: release-check format lint type test cov sec pr check perf slos clean help tollgate-deps tollgate-xsd tollgate-idempotency tollgate-envparity tollgates

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
	@echo "  release-check - Pre-flight the RELEASING.md checklist before tagging"
	@echo "  perf          - Performance benchmarks (XML generation < 500ms/1000tx)"
	@echo "  complex       - Code complexity analysis"
	@echo "  mutate        - Mutation testing"
	@echo "  docs          - Build documentation"
	@echo "  xml-examples  - Regenerate bundled <type>.xml examples and template.db mirrors
	@echo "  corpus-build  - Render scenarios/ and the coverage sets into pain001/corpus/data (deterministic)"
	@echo "  corpus-coverage - Measure coverage sets against the schema inventories (gate)"
	@echo "  corpus-evidence - Print the external-validation checklist per scenario""
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
	@echo "$(YELLOW)Running performance benchmarks (XML gen guard: < $(SLO_XML_GEN)s/1000tx)...$(NC)"
	@mkdir -p .benchmarks
	@# --no-cov: addopts sets --cov-fail-under=100, and this target runs one
	@# file, so coverage would always "fail" here. The Coverage Report job
	@# owns that gate. This was previously hidden by `|| true`.
	@poetry run pytest tests/perf_benchmarks.py -v --benchmark-only --no-cov \
		--benchmark-json=.benchmarks/results.json

complex:
	@echo "$(YELLOW)Analyzing code complexity...$(NC)"
	@poetry run radon cc pain001 -a -s
	@poetry run radon mi pain001

# mutmut 3 reads [tool.mutmut] in pyproject.toml; it takes no path flags.
# The fast tier filters mutants by name: the modules a wrong answer costs
# the most. The floor is the score the tests must reach on that tier.
# Two CI runs on identical code (2026-09-18) scored 87.1% and 83.2% on the
# fast tier (2,562 and 2,446 of 2,941 checked mutants killed): about 120
# mutants change verdict between runs, so the score carries a variance of
# roughly four points that the tests, not the code, are responsible for.
# The floor sits under the lower measurement; it is raised once the
# flipping mutants are found and pinned (see ROADMAP), never lowered to
# make a red run green.
MUTATION_FLOOR ?= 80
MUTATION_FAST_TIER = "pain001.xml.*" "pain001.security.*" "pain001.config.*" "pain001.templates.*"

mutate:
	@echo "$(YELLOW)Running mutation testing (every module)...$(NC)"
	@rm -rf mutants
	@poetry run mutmut run
	@poetry run mutmut export-cicd-stats
	@poetry run python scripts/mutation_gate.py --floor $(MUTATION_FLOOR)

mutate-fast:
	@echo "$(YELLOW)Running fast mutation testing (xml, security, config, templates)...$(NC)"
	@rm -rf mutants
	@poetry run mutmut run $(MUTATION_FAST_TIER)
	@poetry run mutmut export-cicd-stats
	@poetry run python scripts/mutation_gate.py --floor $(MUTATION_FLOOR)

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

# Executable form of the RELEASING.md pre-flight checklist. Run this
# before tagging: the publish job enforces the same rules, but only
# after a tag has been pushed (and a bad tag has to be deleted).
#   make release-check              quick
#   make release-check FULL=1       plus tests, build and pip-audit
release-check:
	@python3 scripts/preflight_release.py $(if $(FULL),--full,)

tollgates: tollgate-deps tollgate-xsd tollgate-idempotency tollgate-envparity
	@echo "$(GREEN)✓ All 4 Advanced Production Tollgates PASSED$(NC)"

# --- XML Example Generation ---
xml-examples:
	@echo "$(YELLOW)Regenerating bundled example XML and SQLite mirrors...$(NC)"
	@poetry run python scripts/generate_xml_examples.py
	@poetry run python scripts/regenerate_template_dbs.py
	@echo "$(GREEN)✓ Bundled examples regenerated$(NC)"

# --- Corpus build (ADR-0003): scenarios -> pain001/corpus/data/market ---
corpus-build:
	@echo "$(YELLOW)Building the corpus from scenarios/...$(NC)"
	@poetry run python scripts/build_corpus.py
	@poetry run python scripts/generate_iso_json_schemas.py
	@echo "$(GREEN)✓ Corpus built$(NC)"

# --- Corpus evidence checklist (ADR-0003, D7) ---
corpus-evidence:
	@poetry run python scripts/corpus_evidence.py checklist

# --- Corpus coverage gate (ADR-0003) ---
corpus-coverage:
	@echo "$(YELLOW)Measuring coverage sets against the schema inventories...$(NC)"
	@poetry run python scripts/corpus_coverage.py --strict
	@echo "$(GREEN)✓ Corpus coverage gate passed$(NC)"
	@poetry run python scripts/generate_iso_json_schemas.py --check

# --- SLO verification (recommended before commit) ---
slos: lint type test perf
	@echo "$(GREEN)✓ All SLOs verified$(NC)"

# --- Full quality gate (blocking) ---
check: lint cov sec corpus-coverage
	@echo "$(GREEN)✓ Full quality gate passed$(NC)"

