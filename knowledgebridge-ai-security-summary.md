# KnowledgeBridge-AI Security Scan Summary

Date: 2026-10-18. Scope: `app.py`, `src/`, `scripts/`, `tests/`, `work/`, dependencies in `.venv`, git history (2 commits). Checklist source: `security-tests.md`.

## Tools run

All installed in a throwaway venv outside the project (Python 3.13). The project `.venv` and `pyproject.toml` were not changed.

| Tool | Version | Target |
|---|---|---|
| Bandit | 1.9.4 | `src app.py scripts` (plus `tests`, `work` as informational) |
| Semgrep | 1.181.0 | rulesets p/python, p/security-audit, p/owasp-top-ten on `app.py src scripts tests` (git-tracked files) |
| pip-audit | 2.10.1 | installed packages in project `.venv` (73 packages) |
| Safety | 3.8.1 | frozen list of `.venv` (`safety check`, open-source DB) |
| gitleaks | 8.30.1 (preinstalled) | git history and working directory (`.venv` excluded) |
| TruffleHog / git-secrets | not available | gitleaks used instead (no uv/pipx/brew install path available) |
| Manual Streamlit review | n/a | grep and code read |

## Findings

| # | Severity | Location | Tool | Status |
|---|---|---|---|---|
| 1 | Medium (Bandit) | `src/knowledgebridge/index_repository.py` lines 173, 352, 632 (B608 SQL string building) | Bandit | False positive; suppressed with `# nosec B608` |
| 2 | Info | `docs/evidence/milestone5/*.json` line 10 (gitleaks `generic-api-key`, 2 hits) | gitleaks | False positive |
| 3 | Unrated (5 advisories) | chromadb 1.5.9: PYSEC-2026-311 (CVE-2026-45829), -3814 (CVE-2026-45833), -3815 (CVE-2026-45831), -3813 (CVE-2026-45830) | pip-audit, Safety | Accepted risk; no fixed version exists (1.5.9 is the latest release) |
| 4 | Unrated | onnxruntime 1.23.2 (2 advisories, Safety's first run only) | Safety | Needs owner review; see remaining items |
| 5 | Low (test code only) | `tests/`, `work/`: B101 asserts, B311, B404/B603 subprocess, B108 /tmp | Bandit | Accepted, out of scope (not shipped code) |

Semgrep: 0 findings. Bandit on shipped code: 0 findings after suppression.

## What was fixed and how

No real vulnerabilities were found in the code, so nothing needed a functional fix. Only change: three `# nosec B608` comments in `src/knowledgebridge/index_repository.py`. The three Bandit hits interpolate a table name into SQL. The name comes from `fts_table()`, which accepts only strings matching `kb_[0-9a-f]{32}` and raises otherwise. All values are bound with `?` parameters.

Side effect: Bandit prints "nosec encountered but no failed test" warnings for the comments on lines 352, 632 and 633. The comments are harmless, and the line 173 comment is the one doing the suppressing. The owner can tidy them if desired.

## False positives and accepted risks

- **B608 (SQL):** see above. Identifier allowlisted by regex, values parameterized.
- **gitleaks `generic-api-key`:** the match is a SHA-256 hex digest of `api_reference.md` stored in evaluation evidence JSON, not a credential. No secrets were found in history or the working tree. `.env`, `data/`, `work/`, `outputs/` and `.streamlit/secrets.toml` are gitignored.
- **chromadb advisories:** all four concern the Chroma HTTP server (pre-auth code injection through `trust_remote_code` in the collections API, and RBAC/tenant authorization flaws). The app only uses embedded `chromadb.PersistentClient` (`index_repository.py:131`). It runs no Chroma server, uses no Chroma auth/RBAC, and never sets `trust_remote_code`. Not reachable. No patched version is published; re-check periodically.
- **Test and work scripts:** Bandit findings in `tests/` and `work/` are test idioms.

## Streamlit-specific checks

- `unsafe_allow_html`: none in the codebase.
- Pickle and caching: no `pickle`, `st.cache_data` or `st.cache_resource`. `session_state` holds only app-generated dicts and strings.
- Config parsing: `yaml.safe_load` only. No `eval`, `exec`, `shell=True` or `verify=False`.
- Uploads: `.streamlit/config.toml` sets `maxUploadSize = 10` MB. Uploaded names are used only for extension lookup and title, never as filesystem paths. The DOCX parser rejects `..` and absolute paths in archive member names. Encrypted PDFs are rejected.
- Network exposure: server bound to `127.0.0.1`, headless, usage stats off, `showErrorDetails = "none"`.
- Secrets: no API keys in code. No `st.secrets` use needed at present.
- Authentication: none, by design (local single-user app). Needs the owner's attention if the app is ever hosted; see below.

## Remaining and needing the owner

1. **Authentication:** if the app is deployed beyond localhost, add streamlit-authenticator or an identity-aware proxy (OAuth2-Proxy, Keycloak, Authentik). Not needed for local use.
2. **onnxruntime 1.23.2:** Safety flagged it once; a later rerun and pip-audit reported none, so Safety's output was inconsistent (the open-source DB or network). `uv.lock` pins 1.23.2 for macOS x86_64 only (`required-environments`) and newer 1.31.0 for other platforms. Please re-run `safety scan` with an account, or confirm via the advisory page, and decide whether macOS x86_64 can move.
3. **chromadb:** watch for a release above 1.5.9 that fixes the advisories.
4. **Dependabot or Snyk:** the checklist lists these; enabling Dependabot on the GitHub repo is an owner action (not done).
5. **TruffleHog:** not run (not installable here). gitleaks covers the same ground; run TruffleHog separately if desired.

## Test results

- `pytest`: 140 passed (before and after the change).
- `ruff check src app.py`: pass. `mypy`: no issues in 19 source files.
- Scanner re-run after the change: Bandit 0 issues, Semgrep 0 findings.

## Files changed

- `src/knowledgebridge/index_repository.py` (3 comment-only edits)
- `knowledgebridge-ai-security-summary.md` (new)
- The pre-existing uncommitted change to `docs/knowledgebridge-ai-milestone-6-portfolio-prep.md` was left untouched. Nothing committed or pushed.
