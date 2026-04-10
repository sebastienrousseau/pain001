# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in pain001, please email **security@pain001.com** instead of using the issue tracker.

Please include:
1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (if available)

We will acknowledge receipt within 48 hours and provide updates on remediation timeline.

## Security Standards

Pain001 focuses on local file processing and generation, so the current
security posture is centered on input handling rather than network-facing
controls:

- **Input Validation**: payment rows, paths, and schema/template combinations are validated before generation.
- **Secrets Protection**: the library does not ship embedded credentials or secrets.
- **XXE Prevention**: XML parsing for inbound reports uses `defusedxml`.
- **Template Safety**: XML templates are rendered through a sandbox and filesystem-expanding Jinja directives are blocked.
- **Path Safety**: data, template, and schema paths are constrained to approved directories.
- **PII Minimization**: structured logging redacts IBAN/BIC/name fields, and validation errors avoid dumping raw payment rows.

## Cryptography Status

The library currently depends on `cryptography` as a transitive/runtime package
constraint, but it does **not** implement payment signing, encryption,
certificate validation, or password hashing features itself. Claims about
AES/bcrypt/argon2 usage would be inaccurate for the current codebase.

## Dependency Security

- Weekly Dependabot scans for CVEs
- Security updates prioritized: critical (7 days), high (30 days), medium (60 days)
- Transitive dependency auditing with `poetry show --tree`
- SBOM generation via CycloneDX for supply chain transparency

## Continuous Integration

- PR and quality workflows run linting, targeted type checks, tests, and release guardrails.
- Mutation and benchmark jobs are available for focused validation of critical paths.
- Dependency and code-scanning workflows remain the main automated controls for CVE and static analysis coverage.

## Codecov Setup

The project uses Codecov for coverage tracking. To enable Codecov in your fork:

1. Visit https://codecov.io and sign in with your GitHub account
2. Enable coverage for the pain001 repository
3. Codecov will automatically detect coverage.xml uploads from GitHub Actions
4. Coverage badge will appear once first upload is processed

**Note**: The Codecov token (`AaUxKfRiou`) is stored in the badge URL for public repositories. For private repos, use GitHub Secrets:

```bash
# In GitHub Settings → Secrets → New repository secret
CODECOV_TOKEN=<your-codecov-token>
```

## Contact

- **Email**: security@pain001.com
- **GitHub Issues**: https://github.com/sebastienrousseau/pain001/security/advisories
- **GitHub Discussions**: https://github.com/sebastienrousseau/pain001/discussions
