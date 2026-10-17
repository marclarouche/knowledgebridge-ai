# Milestone 5 acceptance evidence

The PRD allows milestone 5 to finish with documented blockers that prevent release. This matrix records software evidence without treating fixture-model tests as real model quality evaluation. Final development-run measurements appear in the milestone 5 completion report. No v1 release readiness or human benchmark pass is claimed.

| Criterion | Evidence | Assessment |
|---|---|---|
| AC-001 supported formats and source IDs | All eight fictional samples; TXT/MD/DOCX/PDF parser and metadata regression tests | Functional pass |
| AC-002 reject malformed/unsupported input | Empty/corrupt/unsupported, encrypted/image-only PDF, DOCX archive/DTD, size/count and YAML limit tests | Functional pass within documented parser limits |
| AC-003 valid locations | Exact decoded slices, offsets, PDF page references, DOCX section/table order and stable identity tests | Functional pass |
| AC-004 local embeddings | Real installed embeddinggemma run over all 31 demo passages; model identity/dimension checks | Development verification pass |
| AC-005 exact keyword retrieval | Exact-term development cases, keyword/FTS query tests | Functional pass; annotation-based recall reported separately |
| AC-006 semantic paraphrases | Real-model semantic development evaluation | Provisional quality evidence; human benchmark pending |
| AC-007 ranked deduplicated hybrid results | RRF/dedup regression tests and all development queries | Functional pass; imperfect recall is not hidden |
| AC-008 supported answers with valid citations | Structured answer/citation mechanics tests and live answer development run | Release quality blocker: human support review missing; examine unanswered/failed supported cases |
| AC-009 explicit evidence abstention | Missing-evidence/no-context fixtures and live unsupported/partial/injection questions | Provisional only; failure statuses are not counted as correct abstention |
| AC-010 conflict warning/abstention | Two-source conflict fixtures plus live unscoped/version-scoped cases | Provisional only; single live conflict case cannot establish robust quality |
| AC-011 source inspection | Answer-to-source UI integration and active exact-quote resolution tests | Functional pass |
| AC-012 replacement invalidation | Replacement rollback, new content retrieval, old reference/generation rejection, UI stale form tests | Functional pass |
| AC-013 active content deletion | Keyword/vector/source removal, pending-import preservation, collection isolation/tombstone tests | Functional pass; logical deletion, not forensic erasure |
| AC-014 model unavailable leaves saved index | Timeout/unavailable/identity-change tests and offline UI error handling | Functional pass |
| AC-015 hostile sources cannot execute/fetch/write | Inert injection canary test, source-as-data prompt boundary, no execution imports/API, loopback transport restrictions, hostile FTS identifier/query test | Pass in tested paths; not a native-code sandbox/security guarantee |
| AC-016 preinstalled offline operation | Socket-denied fixture pipeline/UI tests and real local models under evaluator's loopback-only Python audit guard | Application-level verification; OS air-gap and separate server traffic not verified |
| AC-017 engine independent of Streamlit | AST dependency test across all core modules, no Streamlit imports | Pass |
| AC-018 passing tests and documented limitations | Full pytest, Ruff, strict mypy, dependency audit, completion report | Recorded software checks pass; audit findings remain open |

## Release blockers

1. PRD section 14's **at least 30 human-authored questions** and independent human answer-support evaluation are not available. The 33 AI-authored cases remain development evidence. Support accuracy is explicitly null.
2. Real-model behavior and latency must be assessed against product expectations. Supported answer coverage, missed conflicts, false answers, incorrect abstention, validation failures and timeouts in the final results require triage. No automatic pass threshold or human acceptance is invented.
3. Dependency audit findings remain unresolved for Chroma. The embedded Rust client, explicit embeddings, disabled telemetry and lack of a Chroma HTTP server reduce exposure to the documented server/configuration paths, but do not constitute a clean audit. Resolve, replace or explicitly accept the remaining risk before release.

Milestone 6 preparation can use this evidence and its limitations; it must not remove these blockers or claim a validated release without new evidence. The complete user walkthrough remains deferred as requested.
