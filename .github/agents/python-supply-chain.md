# Python Supply Chain Security Tollgate

## Mission
Prevent supply chain attacks and ensure dependency integrity in payment processing.

## Tollgate Objectives
- Enforce **SBOM (Software Bill of Materials)** generation
- Validate **dependency licenses** (no GPL, AGPL)
- Check **known CVEs** in dependencies (zero tolerance)
- Verify **dependency signatures** and checksums
- Detect **typosquatting** and malicious packages

## When This Tollgate Applies
- Adding new dependencies to `pyproject.toml`
- Updating existing dependencies
- Before every release
- Monthly security audits

## Tollgate Checks

### 1. SBOM Generation (MANDATORY for Releases)
```bash
# Option 1: Use Syft (external CLI - no GPL dependencies)
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh
syft packages dir:. -o cyclonedx-json > sbom.json

# Option 2: Use pip-licenses for simple license audit
poetry run pip-licenses --format=json --with-urls > licenses.json

# Option 3: Use Trivy (Docker/GitHub Actions)
trivy fs --format cyclonedx --output sbom.json .

# Output: sbom.json (Software Bill of Materials)
# Contains: All dependencies, versions, licenses, checksums
```

**Success Criteria:**
- SBOM generated successfully
- All dependencies listed with versions
- Licenses identified for all packages
- Checksums present

**Note:** We use external SBOM tools instead of Python packages (e.g., cyclonedx-bom) to avoid GPL-licensed transitive dependencies (rfc3987). See Case Study below.

### 2. License Compliance (MANDATORY)
```bash
# Check all dependency licenses
poetry run pip-licenses --format=markdown --with-urls \
  --fail-on="GPL;AGPL;SSPL;Commons Clause"

# Allowed licenses:
# - MIT, Apache-2.0, BSD-3-Clause, BSD-2-Clause
# - ISC, PSF, MPL-2.0
# - LGPL (acceptable for library use - no linking restrictions for Python)
# - Multi-licensed (e.g., BSD/GPL/PSF - use non-copyleft option)

# Forbidden licenses:
# - GPL v2+, GPL v3+ (strong copyleft - incompatible with Apache 2.0)
# - AGPL (network copyleft - incompatible with Apache 2.0)
# - SSPL (non-OSI approved)
# - Commons Clause (restricts commercial use)
```

**Success Criteria:**
- Zero copyleft licenses (GPL/AGPL)
- All licenses compatible with Apache 2.0
- No proprietary or restrictive licenses

### 3. CVE Scanning (MANDATORY Before Commit)
```bash
# Scan for known vulnerabilities
poetry run pip-audit --format json

# Alternative: use pip-audit
poetry run pip-audit --desc --fix-dryrun

# Check GitHub Advisory Database
gh api /repos/sebastienrousseau/pain001/dependabot/alerts
```

**Success Criteria:**
- Zero HIGH or CRITICAL CVEs
- MEDIUM CVEs with mitigation plan
- Advisory reviewed and acknowledged

### 4. Dependency Checksum Verification
```bash
# Verify Poetry lock file integrity
poetry check  # Validates pyproject.toml and poetry.lock sync

# Alternative: Verify lock file is up-to-date
poetry lock --no-update  # Regenerate lock without updating versions

# Verify pip package checksums
poetry run pip hash requests==2.31.0

# Expected: SHA256 checksum matches PyPI
```

**Success Criteria:**
- `poetry.lock` matches `pyproject.toml`
- All package checksums verified
- No tampered packages detected

### 5. Typosquatting Detection
```bash
# Check for typosquatting attacks
poetry run python scripts/check_typosquatting.py

# Detects:
# - "requsets" instead of "requests"
# - "python-dateutil" vs "python-dateutill"
# - Suspicious package names
```

**Success Criteria:**
- All package names verified against PyPI
- No known typosquat packages
- Dependency names match official repos

### 6. Transitive Dependency Audit
```bash
# Show full dependency tree
poetry show --tree

# Check for:
# - Hidden dependencies
# - Unexpected transitive deps
# - Outdated nested dependencies
```

**Success Criteria:**
- All transitive dependencies known
- No unexpected dependencies
- Transitive deps also security-scanned

### 7. Dependency Pinning (MANDATORY)
```bash
# Verify all dependencies are pinned
grep -E "\\^" pyproject.toml

# Should NOT use ^ (caret) for production
# Should use exact versions: requests = "2.31.0"
```

**Success Criteria:**
- All dependencies pinned to exact versions
- `poetry.lock` committed to git
- Reproducible builds guaranteed

### 8. Private Package Registry Check
```bash
# Verify all packages from trusted sources
poetry config repositories.pypi https://pypi.org/simple/

# Block private/untrusted registries
poetry config -- http-basic.private-registry false
```

**Success Criteria:**
- All packages from PyPI or approved mirrors
- No private registries without security review
- TLS required for all package downloads

## Red Lines (NEVER Violate)

- ❌ NEVER add dependencies without license check
- ❌ NEVER ignore HIGH/CRITICAL CVEs
- ❌ NEVER use packages from untrusted sources
- ❌ NEVER deploy with GPL/AGPL dependencies
- ❌ NEVER skip SBOM generation for releases
- ❌ NEVER use unpinned versions in production

## Supply Chain Attack Scenarios

### Scenario 1: Typosquatting
**Attack**: `requests` → `requsets` (malicious package)
**Defense**: Automated typosquat detection script

### Scenario 2: Dependency Confusion
**Attack**: Private package name hijacked on PyPI
**Defense**: Use private registry with priority

### Scenario 3: Compromised Package Update
**Attack**: Maintainer account compromised, malicious update pushed
**Defense**: Pin exact versions, review all updates

### Scenario 4: Transitive Dependency Injection
**Attack**: Trusted package A depends on malicious package B
**Defense**: Audit full dependency tree, scan ALL deps

## Typosquatting Detection Script

```python
# scripts/check_typosquatting.py
"""Detect typosquatting in dependencies."""
import sys
from difflib import SequenceMatcher
import tomli

KNOWN_PACKAGES = {
    "requests", "urllib3", "certifi", "click", "jinja2",
    "markupsafe", "defusedxml", "xmlschema", "pytest",
    "black", "ruff", "mypy", "bandit", "safety"
}

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def check_typosquat(package_name):
    """Check if package name is suspiciously similar to known package."""
    for known in KNOWN_PACKAGES:
        if package_name == known:
            continue
        sim = similarity(package_name.lower(), known.lower())
        if 0.8 < sim < 1.0:  # 80-99% similar = suspicious
            return known, sim
    return None, 0

def main():
    with open("pyproject.toml", "rb") as f:
        config = tomli.load(f)
    
    deps = config["tool"]["poetry"]["dependencies"]
    
    suspicious = []
    for pkg in deps.keys():
        if pkg == "python":
            continue
        match, sim = check_typosquat(pkg)
        if match:
            suspicious.append((pkg, match, sim))
    
    if suspicious:
        print("❌ TYPOSQUATTING DETECTED!")
        for pkg, match, sim in suspicious:
            print(f"  - '{pkg}' is {sim:.0%} similar to '{match}'")
        sys.exit(1)
    else:
        print("✓ No typosquatting detected")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

## SBOM Integration with Releases

```yaml
# .github/workflows/release.yml
- name: Generate SBOM
  run: |
    poetry run cyclonedx-py -p -o bom.json
    poetry run cyclonedx-py -p -o bom.xml -f xml
  
- name: Upload SBOM to Release
  uses: actions/upload-release-asset@v1
  with:
    asset_path: ./bom.json
    asset_name: pain001-${{ github.ref_name }}-sbom.json
    asset_content_type: application/json
```

## License Compatibility Matrix

| Your License | Compatible Deps | Incompatible Deps |
|--------------|----------------|-------------------|
| Apache 2.0 | MIT, BSD, Apache, ISC, PSF | GPL, AGPL, SSPL |
| MIT | MIT, BSD, Apache, ISC, Unlicense | GPL, AGPL |
| BSD-3 | MIT, BSD, Apache, ISC | GPL, AGPL |

## Dependency Update Policy

1. **Security updates**: Apply immediately (< 24h)
2. **Minor updates**: Review weekly, apply if safe
3. **Major updates**: Review monthly, test thoroughly
4. **Breaking updates**: Plan migration, test extensively

## CVE Response SLA

| Severity | Response Time | Action |
|----------|--------------|--------|
| CRITICAL | < 4 hours | Hotfix + emergency release |
| HIGH | < 24 hours | Patch + release within 48h |
| MEDIUM | < 1 week | Patch + include in next release |
| LOW | < 1 month | Review + update in regular cycle |

## Integration with CI/CD

```yaml
# .github/workflows/supply-chain.yml
name: 🔐 Supply Chain Security

on:
  push:
  schedule:
    - cron: "0 0 * * 1"  # Weekly Monday scan

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: CVE Scan
        run: poetry run pip-audit --format json
      
      - name: License Check
        run: poetry run pip-licenses --fail-on="GPL;AGPL"
      
      - name: Typosquatting Check
        run: poetry run python scripts/check_typosquatting.py
      
      - name: Generate SBOM (using Syft)
        run: |
          curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh
          syft packages dir:. -o cyclonedx-json > bom.json
      
      - name: Upload SBOM
        uses: actions/upload-artifact@v3
        with:
          name: sbom
          path: bom.json
```

## Why This Matters

- **Trust**: Users trust pain001 with financial data
- **Compliance**: Many industries require SBOM (e.g., FDA, NIST)
- **Legal**: License violations can cause lawsuits
- **Security**: Supply chain attacks are increasing (SolarWinds, Log4j)
- **Reputation**: One malicious dependency destroys project credibility

## Success Metrics

- Zero CVEs in production
- 100% license compliance
- SBOM available for every release
- No supply chain incidents
- Dependency updates within SLA

## Case Study: GPL License Violation (2026-01-12)

**Incident:** Supply Chain tollgate discovered GPL v3+ license violation during validation.

**Root Cause:**
- `cyclonedx-bom` package added for SBOM generation
- Pulled in `jsonschema[format]` as transitive dependency
- `jsonschema[format]` includes `rfc3987` (GPL v3+ licensed)
- GPL v3+ incompatible with pain001's Apache 2.0 license

**Dependency Chain:**
```
pain001 (Apache 2.0)
└── cyclonedx-bom ^4.0.0
    └── cyclonedx-python-lib >=7.3.0
        └── jsonschema[format] >=4.18,<5.0
            └── rfc3987 * (GPL v3+)  ← VIOLATION
```

**Detection:**
```bash
$ poetry run pip-licenses --format=markdown | grep GPL
| rfc3987 | 1.3.8 | GNU General Public License v3+ (GPLv3+) |
```

**Impact:**
- 🔴 CRITICAL: Apache 2.0 + GPL v3+ = License conflict
- 🔴 BLOCKING: Cannot release or deploy with this dependency
- ⚠️ LEGAL: Potential copyright infringement if shipped

**Resolution:**
```bash
# Remove GPL-problematic package
poetry remove cyclonedx-bom

# Result: Removed 23 packages including rfc3987
# Alternative: Use external SBOM tools (syft, trivy)
```

**Lessons Learned:**
1. ✅ **Tollgate worked**: Caught issue before production
2. ✅ **Transitive deps matter**: Not just direct dependencies
3. ✅ **External tools preferred**: Avoid pulling in heavy SBOM generators
4. ⚠️ **Check before adding**: Always run license scan on new packages

**Prevention:**
- Always run `poetry run pip-licenses` before committing new dependencies
- Use `--fail-on="GPL;AGPL"` in CI/CD to catch violations automatically
- Prefer external CLI tools (syft, trivy) over Python packages for tooling
- Document dependency justification in PR descriptions

**Time to Resolution:** <10 minutes (detection to fix)
**Cost Avoided:** Potential legal liability + emergency hotfix deployment
