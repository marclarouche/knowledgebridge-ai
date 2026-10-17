# KnowledgeBridge AI — Bandit and Semgrep review

Scanned October 16, 2026. Commit: `6089240024e974aa644dbe4993837da485e5604b` (`main`). The source tree is unchanged and clean after scanning. No source changes, suppressions, commits or pushes were made. Milestone 6 remains paused.

## Results

| Tool/scope | Coverage | High | Medium | Low | Findings |
|---|---:|---:|---:|---:|---:|
| Bandit 1.9.4 — application + scripts | 24 Python files / 3,576 lines | 0 | 3 | 0 | 3 |
| Bandit 1.9.4 — application + scripts + tests | 31 Python files / 5,486 lines | 0 | 4 | 267 | 271 |
| Semgrep CE 1.180.0 — all tracked Python | 31 files / 200 applicable rules | — | — | — | 0 |

Both tools completed without target-parse/scan errors in their JSON reports. Bandit's exit code was 1 because it found issues; Semgrep's was 0. No findings were hidden using `nosec` or `nosemgrep` comments. Semgrep used the registry configurations `p/python` and `p/security-audit`: 346 rules were loaded, of which 200 applied to these targets. This is the Community Edition local scan, not Semgrep Pro, a dependency scan, or a penetration test.

## Application-code triage

Bandit B608, medium severity / medium confidence, flagged `src/knowledgebridge/index_repository.py` lines **173, 352 and 632** for dynamically constructed SQL.

**Assessment: reviewed false positives in the current implementation.** The interpolated portions are FTS table identifiers. Before interpolation, `fts_table()` at line 45 validates the entire identifier with `re.fullmatch(r"kb_[0-9a-f]{32}", generation)` and rejects anything else. The load/build operations assign their table names from this function, and keyword retrieval invokes it directly. Passage text, query expressions and limits use bound SQLite parameters. Untrusted question/document text is not interpolated into SQL.

The existing regression `test_dynamic_fts_identifiers_and_query_payloads_cannot_become_sql` checks hostile identifiers and queries and verifies that the snapshot remains intact. These protections explain why the warnings are not actionable SQL-injection vulnerabilities in the scanned code. The raw warnings remain in the reports; no suppression was added. Changes to table-name validation or future SQL construction require renewed review.

## Test-only triage

- **B101: 262 low-severity findings.** Pytest assertions in tests, not application authorization or security enforcement. Running Python with optimization can remove assertions, so run the test suite normally, without `-O`.
- **B404/B603: four low-severity findings.** Two subprocess imports and two subprocess calls in the review-CLI and offline-guard tests. They invoke the current Python interpreter with fixed repository scripts or a fixed inline verification program, using argument lists and no shell. They do not execute document-provided commands.
- **B311: one low-severity finding**, `tests/test_chunker_ui.py:79`. Seeded pseudorandom input generation for reproducible chunking edge cases; not cryptographic randomness or token generation.
- **B108: one medium-severity finding**, `tests/test_security_offline.py:52`. `/tmp/untrusted.sock` is an inert string passed to the guard's rejection test. The test does not create or open this socket or an insecure temporary file.

Total test-only findings: **268**. These were reviewed as intentional test constructs, not application vulnerabilities. The 271 raw findings are retained rather than silently filtered away.

## Scope and execution

Bandit was installed into an isolated environment in the chat work directory. The project's virtual environment, `pyproject.toml`, `uv.lock`, local library and runtime settings were not changed.

The first Semgrep scan covered 24 application/script files but skipped seven test files through its default test-directory ignores. For the full scan, all 31 Git-tracked Python files were copied byte-for-byte into a scratch snapshot with a comment-only `.semgrepignore`. File hashes were checked against the original source before and after analysis. This follows Semgrep's documented [default-ignore override](https://docs.semgrep.dev/ignoring-files-folders-code#override-defaults) while leaving the repository configuration untouched. The source manifest records each SHA-256.

Semgrep downloaded registry rules, with metrics and version checks disabled. Analysis ran locally; no AppSec Platform scan, login, result upload, autofix or secret validation was requested. The installed Semgrep initially failed to access certificate trust anchors under the restricted sandbox. Retrying with normal macOS trust-store access succeeded; certificate verification was not disabled. Its native wrapper printed signal-handler warnings, but the scans completed and the JSON error arrays were empty.

No live collection data, virtual environments, model files, dependency source trees, PDFs/DOCX samples, or Git history were included in the Python SAST scan. The separate known Chroma dependency advisories from milestone 5 remain unresolved; Semgrep's zero code findings do not clear those advisories or the human-evaluation/model-quality release blockers.

## Reproduce

Run Bandit from the project root with Python 3.12:

```sh
bandit -r app.py src scripts --ignore-nosec -f json -o /tmp/knowledgebridge-bandit-application.json
bandit -r app.py src scripts tests --ignore-nosec -f json -o /tmp/knowledgebridge-bandit.json
```

For a full Semgrep run, use a hash-identical scratch copy of tracked Python files and a comment-only `.semgrepignore` in that scratch root, then run:

```sh
semgrep scan --config p/python --config p/security-audit \
  --metrics off --disable-version-check --disable-nosem \
  --strict --error --jobs 2 --timeout 15 --include '*.py' \
  --json-output /tmp/knowledgebridge-semgrep.json app.py src scripts tests
```

Registry rules can change over time; a future run may produce different results. The recorded versions and JSON files describe this run. A clean static scan does not prove the absence of vulnerabilities.

## Saved evidence

- [Bandit application/script results](evidence/security/knowledgebridge-bandit-application.json)
- [Bandit complete Python results](evidence/security/knowledgebridge-bandit.json)
- [Semgrep complete Python results](evidence/security/knowledgebridge-semgrep-all-python.json)
- [Initial Semgrep application/script results](evidence/security/knowledgebridge-semgrep.json)
- [Source hashes and commit](evidence/security/knowledgebridge-sast-source-manifest.json)

## Historical scope at publication

These reports describe commit `6089240024e974aa644dbe4993837da485e5604b` from October 16. Subsequent portfolio and answer-validation changes are outside that source manifest. No fresh Bandit/Semgrep pass is claimed for the later changes. The quoted clean source-tree status above refers to the original scan time.
