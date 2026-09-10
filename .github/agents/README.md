# PySentinel Agent Guidelines & Tollgates

## Overview

This directory contains comprehensive quality tollgates for the Pain001 project, implementing a **Zero-Trust** quality model.

## Active Tollgates

### Core Quality Gates (Always Enforced)

1. **[python-quality.md](python-quality.md)** - XSD validation, truth engine, content accuracy
2. **[python-security.md](python-security.md)** - XXE prevention, vulnerability scanning, secure practices
3. **[python-deps.md](python-deps.md)** - Dependency governance, security impact analysis

### Advanced Tollgates (New - High Value)

4. **[python-performance.md](python-performance.md)** - Performance benchmarking, SLO enforcement, regression detection
5. **[python-contracts.md](python-contracts.md)** - API backward compatibility, input source parity, golden file testing
6. **[python-supply-chain.md](python-supply-chain.md)** - SBOM generation, license compliance, CVE scanning, typosquatting detection

## Tollgate Hierarchy

```
Level 1: Baseline Quality (MANDATORY for ALL commits)
├─ Formatting & Linting (ruff, black, isort)
├─ Type Safety (mypy strict mode)
├─ Test Coverage (≥95% floor, 100% for new code)
└─ Security Scanning (bandit, safety - zero HIGH/CRITICAL)

Level 2: Domain-Specific (MANDATORY for specific changes)
├─ XSD Semantic Anchor (template changes)
├─ Content Accuracy Truth Engine (documentation claims)
├─ Dependency Governance (new packages)
└─ Codacy Pre-Flight (local emulation)

Level 3: Advanced Assurance (RECOMMENDED, becoming mandatory)
├─ Performance Regression Testing (core path changes)
├─ API Contract Validation (public API changes)
└─ Supply Chain Security (dependency updates, releases)
```

## Quick Start

### For New Contributors

1. Read [python-quality.md](python-quality.md) - Core requirements
2. Read [python-security.md](python-security.md) - Security red lines
3. Review [python-deps.md](python-deps.md) if adding dependencies

### For Core Maintainers

1. All of the above, plus:
2. [python-performance.md](python-performance.md) - Performance budgets
3. [python-contracts.md](python-contracts.md) - API stability
4. [python-supply-chain.md](python-supply-chain.md) - Release readiness

## Implementation Roadmap

### Phase 1: Already Implemented ✅

- [x] Core quality gates (lint, type, coverage, security)
- [x] XSD validation tollgate
- [x] Content accuracy truth engine
- [x] Dependency governance
- [x] Codacy integration

### Phase 2: New Tollgates (This PR) 🚀

- [x] Performance regression testing framework
- [x] API contract validation guidelines
- [x] Supply chain security checklist

### Phase 3: Automation (Next Sprint)

- [ ] Automated performance benchmarks in CI
- [ ] Golden file generation on release
- [ ] SBOM auto-upload to releases
- [ ] Weekly CVE scanning cron job

### Phase 4: Enforcement (Future)

- [ ] Block PRs with performance regressions
- [ ] Enforce contract tests before merge
- [ ] Mandate SBOM for all releases

## Measuring Success

### Current Metrics (v0.0.44)

- Test Coverage: 99.14% (target: ≥95%)
- Security Vulnerabilities: 0 (target: 0)
- Codacy Grade: A (target: A or B)
- Type Safety: 100% (mypy strict)

### New Metrics (Proposed)

- Performance Regressions: 0 (target: 0)
- API Breaking Changes: 0 (target: 0 without major bump)
- Supply Chain CVEs: 0 (target: 0)
- License Violations: 0 (target: 0)

## Tollgate Decision Matrix

| Change Type | Required Tollgates |
|-------------|-------------------|
| Bug fix | Quality + Security |
| New feature | Quality + Security + Performance (if core path) |
| API change | Quality + Security + Contracts |
| Dependency add | Quality + Deps + Supply Chain |
| Template change | Quality + XSD |
| Documentation | Truth Engine |
| Release | ALL tollgates |

## FAQ

**Q: Why so many tollgates?**
A: Payment processing requires enterprise-grade quality. Each tollgate prevents a specific category of production failures.

**Q: Can I skip a tollgate?**
A: No. Zero-Trust model means no exceptions. If a tollgate fails, fix the issue or escalate.

**Q: What if I disagree with a tollgate rule?**
A: Open an issue for discussion. Rules can be updated, but only after consensus.

**Q: How long do tollgates add to development?**
A: Initial setup: 30min. Per-commit: 2-5min (mostly automated). Value: Prevents hours/days of debugging.

## Contact

- Issues: Use GitHub Issues
- Questions: GitHub Discussions
- Security: See SECURITY.md

---

Last updated: 2026-01-12  
Tollgates: 6 active, 3 planned  
Zero-Trust Model: Enforced
