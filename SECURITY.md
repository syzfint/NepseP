# Security Policy & Defensive Architecture

ApexMarketEngine adheres to institutional security standards to protect financial models, quantitative inference bridges, data pipelines, and market analytics against data tampering, injection vectors, and unauthorized exposure.

---

## Supported Versions

| Version | Supported | Security Notes |
| :--- | :---: | :--- |
| `1.0.x` | :white_check_mark: | Active support; 10-Gate Audit + Clef Provenance Hashing |
| `< 1.0.0` | :x: | Legacy experimental releases; unsupported |

---

## Defensive Architecture & Controls

The repository implements defense-in-depth across the data lakehouse, quantitative engine, and API tiers:

### 1. SQL Injection (CWE-89) Elimination
All DuckDB database queries utilize **parameterized prepared statements** and typed parameter binding (`?` placeholders) or verified filesystem path resolution. Dynamic string interpolation into SQL queries is prohibited and enforced via automated static analysis.

### 2. Cryptographic Data Provenance & Anti-Tamper
All inference payloads passing through the Clef Multimodal Bridge enforce composite SHA-256 provenance hashing (`compute_provenance_hash`). Any modification to quantitative forecasts, market context, or technical charts results in an immediate fail-closed circuit breaker rejection (`PROVENANCE_HASH_MISMATCH` / HTTP 422).

### 3. Server-Side Request Forgery (SSRF - CWE-918) Defense
External service endpoints (such as `CLEF_BASE_URL`) require explicit scheme validation (`http://` or `https://` only) to block file:// protocol smuggling or loopback port scanning.

### 4. Denial-of-Service & Resource Exhaustion Defense (CWE-400)
All outgoing network requests in scrapers and harness connectors enforce explicit connection and read timeouts (`timeout=30s`). Hanging upstream connections cannot starve worker threads.

### 5. Cross-Origin Resource Sharing (CORS) Hardening
API endpoints reject wildcard unrestricted origins by default, restricting access to designated frontend origins (`http://localhost:8501`, `http://127.0.0.1:8501`, etc.) with configurable overrides via `ALLOWED_CORS_ORIGINS`.

### 6. Supply Chain & Model Weight Integrity (CWE-494)
Model downloading and multimodal weight fine-tuning scripts enforce explicit revision pinning and opt-in controls for remote execution (`--trust_remote_code` defaulting to False).

---

## Strix AI Penetration Testing & CI/CD Gating

ApexMarketEngine integrates **[Strix](https://github.com/usestrix/strix)**, the open-source autonomous AI penetration testing tool, directly into its development lifecycle.

### Installed Strix Agent Skills
The workspace is equipped with the official 9-skill Strix offensive testing suite located in `.agents/skills/`:
- `api-security-testing`
- `application-security-testing`
- `ci-security-scanning-with-strix`
- `find-security-vulnerabilities-in-code`
- `fix-security-vulnerabilities-with-strix`
- `managed-pentesting-with-strix`
- `owasp-top-10-testing`
- `penetration-testing-with-strix`
- `web-app-penetration-testing`

### Automated CI/CD Workflow
Every Pull Request and weekly scheduled run triggers `.github/workflows/security.yml`:
- **Bandit SAST**: Scans Python codebase for dangerous constructs (CWE-89, CWE-494, CWE-400).
- **Supply Chain Audit (`pip-audit`)**: Verifies dependencies against the PyPI vulnerability database.
- **Gitleaks**: Audits commit history to prevent accidental credential or API key commits.
- **Strix Autonomous Pentest**: When `STRIX_LLM` and `LLM_API_KEY` are provided in repository secrets, Strix autonomously executes dynamic penetration tests in a sandboxed runtime.

---

## Running Local Security Audits

Developers and auditors can verify codebase security locally with the following commands:

### 1. Static Application Security Testing (Bandit)
```bash
bandit -r scripts/ -ll
```

### 2. Dependency Vulnerability Audit (pip-audit / uv)
```bash
pip-audit -r requirements.txt
# or with uv
uv audit
```

### 3. Strix Autonomous AI Pentest (Local CLI)
```bash
# Requires Docker running and STRIX_LLM / LLM_API_KEY set
export STRIX_LLM="openrouter/z-ai/glm-5.3"
export LLM_API_KEY="your-api-key"
strix -n --target ./ --scan-mode quick --max-budget 10
```

---

## Reporting a Vulnerability

If you discover a security vulnerability or exploit vector in ApexMarketEngine:

1. **Do not** disclose the vulnerability publicly in GitHub issues or public forums.
2. Email a detailed vulnerability report and proof-of-concept to **acharyasayuz98@gmail.com**.
3. Include the affected file, lines of code, environmental prerequisites, and steps to reproduce.
4. Maintainers will acknowledge receipt within 48 hours and work with you to test and deploy a verified patch.
