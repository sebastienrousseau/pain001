# Contributing to Pain001

**Welcome!** Pain001 is an enterprise-grade ISO 20022 payment processing library. We operate under a **Zero-Trust Quality Model** where all contributions must pass strict quality gates before acceptance. This guide explains how to contribute code that meets our production standards.

---

## 🎯 Before You Start: Understanding PySentinel

Pain001 uses **PySentinel**, an automated quality guardian that enforces:

- **95% minimum code coverage** (new code requires 100%)
- **Type safety**: Full type hints, zero `Any` unless justified
- **Security**: XXE prevention (defusedxml), no secrets in logs
- **Standards**: ISO 20022 compliance, Jinja2 autoescape, XSD validation
- **Determinism**: Idempotent processing, no global mutable state

**Red Lines (Absolute Prohibitions):**
- ❌ No commits without running `poetry run make check`
- ❌ No code without type hints
- ❌ No pulling with `pip` (Poetry-only)
- ❌ No unsupported claims (pain.002, RLP, RTP, etc.)
- ❌ No bypassing quality gates under any circumstances

If you see a quality gate fail, STOP. Fix the issue locally. Only then commit.

---

## 📋 Development Environment Setup

### Prerequisites
- **Python 3.9+** (tested on 3.9, 3.10, 3.11, 3.12)
- **Poetry** (dependency manager; required, not pip)
- **Git** (version control)
- **Linux/macOS/Windows** (cross-platform support verified)

### Step 1: Fork & Clone
```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/<your-username>/pain001.git
cd pain001

# Add upstream remote for staying in sync
git remote add upstream https://github.com/sebastienrousseau/pain001.git
```

### Step 2: Install Dependencies with Poetry
```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install project dependencies
poetry install

# Verify installation
poetry run python -c "import pain001; print(f'Pain001 version: {pain001.__version__}')"
```

**Why Poetry?**
- Dependency lock files ensure reproducible builds
- Separates dev, test, and runtime dependencies
- Manages virtual environments automatically
- Required by all CI/CD pipelines

### Step 3: Understand the Codebase

**Key Directories:**
```
pain001/
  ├── core/        # Orchestration: process_files(), workflow
  ├── data/        # Loading: CSV, SQLite, Python data structures
  ├── xml/         # Generation: Jinja2 templates, XSD validation
  ├── csv/         # CSV-specific loading and validation
  ├── db/          # SQLite-specific loading and validation
  ├── cli/         # Command-line interface
  └── constants/   # ISO 20022 version mappings, field definitions
tests/
  ├── test_csv_*.py        # CSV loader tests
  ├── test_db_*.py         # SQLite loader tests
  ├── test_pain001_v*.py   # Version-specific tests (v03-v11)
  └── test_integration.py  # End-to-end workflow tests
```

**Key Concepts:**
1. **Input Sources** (all 4 must work with your changes):
   - CSV files: `.csv` format
   - SQLite databases: `.db` files
   - Python lists: `[{"field": "value"}, ...]`
   - Python dicts: `{"field": "value"}` (wrapped as list internally)

2. **ISO Versions** (all 9 must work with your changes):
   - pain.001.001.03 through pain.001.001.11
   - All support "Customer Credit Transfer Initiation" only
   - No support for pain.002, pain.008, RLP, RTP, RAI, TISS

3. **Data Pipeline:**
   ```
   CSV/SQLite/Python → Loader → Validator → Transformer →
   XML Generator → Jinja2 Renderer → XSD Validator → File Write
   ```

---

## ✅ Before You Code: Pre-Contribution Checklist

- [ ] **Read** [README.md](README.md) for features and usage examples
- [ ] **Understand** the data pipeline architecture (see above)
- [ ] **Check** [ROADMAP.md](ROADMAP.md) for planned features and milestones
- [ ] **Search** [issues](https://github.com/sebastienrousseau/pain001/issues) to avoid duplicates
- [ ] **Install** Poetry and run `poetry install`
- [ ] **Verify** environment with `poetry run make check` (should pass)

---

## 🔧 Making Code Changes

### Step 1: Create a Feature Branch
```bash
# Sync with upstream
git fetch upstream
git checkout -b feature/issue-NNN main

# Example: bug fix, feature request, refactoring
git checkout -b fix/cli-error-handling
git checkout -b feature/json-input-support
git checkout -b refactor/loader-architecture
```

### Step 2: Write Code with Full Type Hints

**Required Pattern:**
```python
def load_payment_data(
    data_source: str | list[dict[str, Any]] | dict[str, Any]
) -> list[dict[str, Any]]:
    """Load payment data from CSV, SQLite, list, or dict.

    Args:
        data_source: File path (str) or Python data structure.

    Returns:
        List of validated payment dictionaries.

    Raises:
        FileNotFoundError: If file path doesn't exist.
        ValueError: If data structure is invalid.
    """
    # Type guard: handle all input types
    if isinstance(data_source, str):
        # File path: CSV or SQLite
        return _load_from_file(data_source)
    elif isinstance(data_source, list):
        # Python list of dicts
        return _load_from_list(data_source)
    elif isinstance(data_source, dict):
        # Single dict: wrap as list
        return _load_from_dict(data_source)
    else:
        raise ValueError(f"Unsupported source type: {type(data_source)}")
```

**Type Hints Checklist:**
- [ ] All function parameters have type hints
- [ ] Return type is specified (never `-> None` unless truly no return)
- [ ] No `Any` without `# type: ignore[specific-code]` comment
- [ ] Use `Union`, `TypeGuard`, `Protocol` for complex types
- [ ] Docstring includes Args, Returns, Raises sections

### Step 3: Write Tests Simultaneously

**Test Requirements:**
- Every new function needs a test
- Every error path needs a test (e.g., FileNotFoundError, ValueError)
- Every input source (CSV, SQLite, list, dict) needs a test
- Every ISO version (if affected) needs a test
- Tests must achieve **100% branch coverage** of new code

**Test Pattern:**
```python
def test_load_payment_data_from_csv() -> None:
    """Test loading payment data from CSV file."""
    csv_path = "tests/test_data/pain001_03_data.csv"

    result = load_payment_data(csv_path)

    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(item, dict) for item in result)


def test_load_payment_data_from_list() -> None:
    """Test loading payment data from Python list."""
    data = [
        {"id": "PAY001", "amount": 100.50, "currency": "EUR"},
        {"id": "PAY002", "amount": 200.00, "currency": "EUR"},
    ]

    result = load_payment_data(data)

    assert result == data  # Should be identical


def test_load_payment_data_invalid_file() -> None:
    """Test loading non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_payment_data("nonexistent.csv")
```

**Create test file:** `tests/test_<module_name>.py` following existing patterns.

---

## 🛡️ Quality Gates: The PySentinel Zero-Trust Model

### Gate 1: Formatting & Linting
```bash
poetry run ruff check pain001 tests       # Linting
poetry run black --check pain001 tests    # Code formatting
poetry run isort --check pain001 tests    # Import sorting
```

**Common Issues & Fixes:**
- **isort errors**: Run `poetry run isort pain001 tests`
- **black errors**: Run `poetry run black pain001 tests`
- **ruff errors**: Run `poetry run ruff check --fix pain001 tests`

### Gate 2: Type Safety
```bash
poetry run mypy .  # Must exit code 0
```

**Expected Output:**
```
Success: no issues found in 42 source files
```

**Common Issues:**
- Missing type hints: Add `-> Type` to function signatures
- Type mismatches: Adjust types or fix logic
- Use `# type: ignore[specific-code]` only with explicit error codes

### Gate 3: Test Coverage (95% Floor, 100% for New Code)
```bash
poetry run pytest --cov=pain001 --cov-report=term
```

**Expected Output:**
```
TOTAL              42   384    2   98.645%
```

**If Coverage < 95%:**
- Identify uncovered lines: `poetry run pytest --cov=pain001 --cov-report=html`
- Open `htmlcov/index.html` in browser
- Add tests for uncovered paths
- Re-run: `poetry run pytest --cov=pain001 --cov-report=term`

### Gate 4: Security Scanning
```bash
poetry run bandit -r pain001 tests  # Security issues
poetry run pip-audit --strict       # Dependency vulnerabilities
```

**Expected Output:**
```
No issues identified in 42 Python files
No vulnerabilities found
```

**Common Issues:**
- Hardcoded secrets: Use `os.getenv("SECRET")`
- Unsafe XML parsing: Use `defusedxml` not `xml.etree`
- Insecure file paths: Use `pathlib` or `os.path.expanduser()`

### Gate 5: Advanced Tollgates (Enterprise Production)

**Run all 4 tollgates:**
```bash
poetry run make tollgates
```

#### Tollgate 1: Dependency Governance
```bash
poetry run make tollgate-deps
```
Ensures: No new packages without security review.

#### Tollgate 2: XSD Semantic Anchor
```bash
poetry run make tollgate-xsd
```
Ensures: Generated XML is ISO 20022 compliant (validates against actual XSD schemas).

#### Tollgate 3: Idempotency
```bash
poetry run make tollgate-idempotency
```
Ensures: Running `process_files()` twice with identical input produces byte-for-byte identical output.

#### Tollgate 4: Environmental Parity
```bash
poetry run make tollgate-envparity
```
Ensures: Code works on Linux, macOS, and Windows (no hardcoded paths, uses `pathlib`).

---

## 🚀 Running the Full Quality Gate (MANDATORY Before Commit)

**This is non-negotiable. No exceptions.**

```bash
# Run entire quality gate
poetry run make check

# Expected output:
# ✓ ruff check (linting)
# ✓ black check (formatting)
# ✓ isort check (imports)
# ✓ mypy . (types)
# ✓ pytest --cov (coverage >= 95%)
# ✓ bandit -r (security)
# ✓ pip-audit (dependencies)
#
# Result: Exit code 0 ✓
```

**If ANY gate fails (exit code ≠ 0):**
1. **STOP**. Do not commit.
2. Read error messages carefully.
3. Fix issues:
   - Formatting: `poetry run black pain001 tests`
   - Imports: `poetry run isort pain001 tests`
   - Types: Edit code to match mypy output
   - Tests: Add missing tests for uncovered code
4. Re-run: `poetry run make check`
5. Once all gates pass (exit code 0), proceed to commit.

**Why this matters:**
- Quality gates catch bugs before they reach production
- Coverage ensures reliability (95% minimum = enterprise grade)
- Type safety prevents runtime errors
- Security scanning prevents vulnerabilities
- Tollgates enforce ISO 20022 compliance and determinism

---

## 📝 Documentation Requirements

**For EVERY commit, update relevant documentation:**

### 1. README.md
- Add feature to "Features" list if applicable
- Update code examples if API changes
- Include new input source or version support

### 2. CHANGELOG.md
- Add entry under "## [Unreleased]"
- Format: `### Added | Fixed | Changed | Deprecated | Removed | Security`
- Link issues: `[#123](https://github.com/sebastienrousseau/pain001/issues/123)`

### 3. Code Docstrings
- Every function needs a docstring with Args, Returns, Raises
- Explain WHY, not just WHAT
- Include examples for complex functions

### 4. Release Notes (For Version Bumps Only)
- Create `releases/vX.Y.Z.md`
- Include: Features, bug fixes, breaking changes, migration guide
- 100-150 lines target

---

## 📤 Commit Message Format (MANDATORY)

```
<type>: <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`, `perf`

**Example:**
```
fix: Handle missing required fields in CSV validation

- Add explicit check for required IBAN/BIC fields
- Provide clear error message with line number
- Add 3 new test cases for missing field scenarios

Resolves #456
Quality Gate: PASSED (exit code 0)
Coverage: 98.645% (≥ 95% floor)
Tests: 385/385 passing
```

---

## 🔄 Pull Request Workflow

### Step 1: Commit Locally
```bash
# Stage changes
git add pain001/module.py tests/test_module.py docs/

# Verify staged changes
git status

# Run final quality gate (MANDATORY)
poetry run make check

# Commit (only if gate passes)
git commit -m "feat: Add new feature

- Implementation detail 1
- Implementation detail 2

Quality Gate: PASSED (exit code 0)
Coverage: 98.645%
Tests: 385/385

Resolves #456"
```

### Step 2: Push to GitHub
```bash
# Push to your fork
git push origin feature/issue-NNN

# GitHub shows PR button automatically
```

### Step 3: Open PR with Complete Description
```
Title: Fix: Handle missing required fields in CSV validation

## Description
This PR fixes issue #456 where missing IBAN/BIC fields in CSV
files cause unclear error messages.

## Changes
- Add explicit validation in validate_csv_data()
- Provide line-number-specific error messages
- Add 3 comprehensive test cases

## Testing
- All 385 tests passing
- Coverage: 98.645%
- Tollgates: PASSED

## Backward Compatibility
✓ All 4 input sources working (CSV, SQLite, list, dict)
✓ All 9 ISO versions tested (v03-v11)
✓ 100% backward compatible

Closes #456
```

### Step 4: Code Review & CI/CD
- GitHub Actions runs quality gate automatically
- Codacy analyzes code quality (must be Grade A or B)
- Maintainers review for architectural alignment
- Address feedback, push fixes to same branch

### Step 5: Merge
- Once all checks pass and maintainers approve
- Merge via "Squash and merge" or "Create a merge commit"
- Delete feature branch

---

## ❓ Common Issues & Solutions

### Issue 1: `poetry: command not found`
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

# Verify
poetry --version
```

### Issue 2: Import sorting conflicts (isort vs black)
```bash
# Make sure pyproject.toml has isort/black config:
[tool.isort]
profile = "black"
line_length = 88

[tool.black]
line-length = 88

# Then run:
poetry run isort .
poetry run black .
```

### Issue 3: Type errors on valid code
```python
# If mypy is overly strict, use specific ignore:
result = func()  # type: ignore[assignment]
# ✓ Good (specific error code)

# NOT:
result = func()  # type: ignore
# ✗ Bad (suppresses all errors)
```

### Issue 4: Tests fail locally but pass in CI
```bash
# Ensure you're using same Python version as CI
poetry env info  # Check Python version

# If different, delete venv and recreate:
poetry env remove <env-name>
poetry install
```

### Issue 5: Can't run make commands
```bash
# Ensure Makefile is readable
chmod +x Makefile

# Run make targets via poetry
poetry run make <target>

# Or run directly:
make <target>
```

### Issue 6: XSD validation fails
```bash
# Check that template file path is correct
ls -la pain001/templates/pain.001.001.03/

# Verify XSD schema exists
ls -la pain001/templates/pain.001.001.03/pain.001.001.03.xsd

# Test generation with explicit paths
poetry run python -c "
from pain001.core.core import process_files
result = process_files(
    xml_message_type='pain.001.001.03',
    data_path='tests/test_data/pain001_03_data.csv',
    xml_template_file_path='pain001/templates/pain.001.001.03/template.xml',
    xsd_schema_file_path='pain001/templates/pain.001.001.03/pain.001.001.03.xsd'
)
print('✓ XSD validation passed' if result else '✗ Failed')
"
```

---

## 🎓 Learning Resources

- **Pain001 README**: [README.md](README.md) - Features, usage examples
- **Roadmap**: [ROADMAP.md](ROADMAP.md) - Planned features and milestones
- **Architecture**: [pain001/core/core.py](pain001/core/core.py) - Main orchestration
- **ISO 20022**: [Documentation](https://www.iso20022.org/) - Payment standards
- **Jinja2**: [Official Docs](https://jinja.palletsprojects.com/) - Template engine
- **Poetry**: [Official Docs](https://python-poetry.org/docs/) - Dependency management

---

## 💬 Getting Help

- **Issues**: Create a new issue with clear description and reproducible steps
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainer for sensitive matters

---

## 📋 Pre-Submit Final Checklist

Before pushing your PR, verify ALL items:

- [ ] **Code Quality**
  - [ ] `poetry run make check` passes (exit code 0)
  - [ ] Coverage ≥ 95% (report actual %)
  - [ ] All linters pass (ruff, black, isort, mypy)
  - [ ] All 385 tests passing
  - [ ] Security scan: 0 vulnerabilities

- [ ] **Type Safety**
  - [ ] All functions have full type hints
  - [ ] No `Any` without specific `# type: ignore[code]`
  - [ ] `poetry run mypy .` returns 0

- [ ] **Testing**
  - [ ] New code has 100% branch coverage
  - [ ] All 4 input sources tested (CSV, SQLite, list, dict)
  - [ ] All affected ISO versions tested (v03-v11)
  - [ ] Error paths tested (exceptions, edge cases)

- [ ] **Tollgates**
  - [ ] `poetry run make tollgates` PASSED
  - [ ] XSD validation: PASSED
  - [ ] Idempotency: PASSED
  - [ ] Environmental parity: PASSED

- [ ] **Documentation**
  - [ ] README.md updated (if feature/API change)
  - [ ] CHANGELOG.md updated (Unreleased section)
  - [ ] Docstrings added to all functions
  - [ ] Commit message follows format

- [ ] **Git**
  - [ ] `git status` shows only staged changes
  - [ ] No untracked files (use .gitignore)
  - [ ] Branch is up-to-date with upstream main
  - [ ] Commit message is descriptive

- [ ] **Backward Compatibility**
  - [ ] All 385 tests passing
  - [ ] All 4 input sources working
  - [ ] All 9 ISO versions working
  - [ ] Zero regressions detected

---

## 🎉 Thank You!

Your contributions make Pain001 better. We're grateful for your time and effort in helping us maintain enterprise-grade payment processing standards.

**Questions?** Open an issue or start a discussion. We're here to help!

---

**Last Updated**: January 2026
**Contact**: [@sebastienrousseau](https://github.com/sebastienrousseau)
**License**: Apache 2.0 & MIT
