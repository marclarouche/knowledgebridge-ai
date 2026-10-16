# KnowledgeBridge AI — Milestone 5 completion

Completed October 16, 2026 in `the project root`. Milestone 5 testing/evaluation work is complete under the PRD exit criterion allowing documented blockers that prevent release. **The product is not cleared for release.** Milestone 6 has not started. The user requested a pause after milestone 5 and the first GitHub commit/push. The full user walkthrough remains deferred until all milestones are finished, as requested.

## Delivered

- Isolated, incremental evaluation CLI for processing, keyword/semantic/hybrid retrieval, local generation, returned-citation integrity, explicit abstention, false-answer and conflict-status measurements.
- A clearly labeled 33-case AI-authored development dataset: the existing 30 retrieval questions plus explicit conflict, partial-evidence and hostile-instruction cases. It is not a human-authored release benchmark.
- Relevance annotation validation, unique case/result checks, exact passage recall denominators and null handling for absent measurements. Generation/validation failures never count as correct abstentions.
- Independent review worksheet/scorer bound to exact answer digests, with duplicate/stale review rejection and separate review coverage. No human reviewer or human support score is invented.
- Python-level loopback-only audit instrumentation plus security/offline/Streamlit regression coverage.
- Reproduction/metric documentation and an AC-001–AC-018 acceptance matrix with release blockers.

## Software checks

**136 tests passed**, with five upstream SWIG deprecation warnings. This includes ingestion, retrieval, answer gates, library lifecycle, source navigation, stale forms, evaluation metrics, review CLI round trip, offline guard enforcement and all nine Streamlit views. Ruff lint and formatting passed. Strict mypy passed across **19 source files**. `pip check` reported no broken requirements. No dependencies were added or changed.

The optional Ruff security-rule scan reported three S608 findings for dynamic internal FTS table identifiers. Each uses a strict `kb_` plus 32 lowercase hexadecimal validator, with text/query values bound as SQLite parameters. Hostile query and identifier tests pass. These are reviewed identifier-construction false positives; the scan findings were not hidden by a global suppression. This is not a penetration test.

The required dependency audit reports **five entries for Chroma 1.5.9, representing four unique advisories**, with no fixed versions reported: PYSEC-2026-311 (duplicated entry), PYSEC-2026-3813, PYSEC-2026-3814 and PYSEC-2026-3815. This is not a clean audit. Existing embedded-only/Rust-client/explicit-vector mitigations and server/configuration exposure limitations remain documented.

## Real local development evaluation

The evaluator imported **8/8 fictional documents**, producing **31 passages**, into a temporary index. The app's live library was not used for evaluation or deleted. Reports record corpus SHA-256 values, dataset digest, exact configuration, installed model identities/digests, platform, passage IDs, case outputs and elapsed times. All report content is fictional development material.

Embedding model: `embeddinggemma:latest`, 768 dimensions. Generation model: `qwen3-vl:4b-instruct`. The main run used an explicit **60-second per-generation-request limit**; the application's configured limit remains 240 seconds. Embedding requests retained the configured 120-second limit. End-to-end answer time can exceed one request's limit because retrieval, model identity checks, drafting and a second model review are separate operations. This is an observational development run, not a controlled performance benchmark.

### Retrieval across all 33 cases

Recall is measured against distinct relevant passage IDs resolved from the supplied filename/substring annotations. Seven cases have no retrieval relevance targets and are excluded from recall denominators. Annotation completeness has not received independent human review.

| Mode | Targeted cases | Macro passage Recall@5 | Target hit rate@5 |
|---|---:|---:|---:|
| keyword | 26 | 96.2% | 96.2% |
| semantic | 26 | 100.0% | 100.0% |
| hybrid | 26 | 96.2% | 96.2% |

Missed annotations: RQ-019 (keyword), RQ-019 (hybrid). Retrieval relevance is not proof that an answer is supported or that an unanswerable question will abstain.

### Main 60-second request-budget answer run

- Attempted answers: 33; statuses: answered=5, validation_failed=1, generation_failed=22, insufficient_evidence=5.
- Supported-answer status coverage: 5/24 (20.8%).
- Correct explicit abstention: 5/8 (62.5%).
- False-answer frequency on annotated unanswerable cases: 0/8 (0.0%).
- Conflict status: 0/1 (0.0%).
- Returned citation validity: 7/7 (100.0%); missing evidence references: 0.
- Independent human answer support accuracy: **not measured**.

End-to-end median: 60.4 seconds; range: 12.9–77.1 seconds. Returned citation validity is conditioned on outputs that survived application validation; rejected drafts and service failures are reported in their status counts. A zero false-answer rate alongside failures is not proof of correct abstention or model safety.

| Case | Category | Expected status | Actual status | Reason | Seconds |
|---|---|---|---|---|---:|
| RQ-001 | exact | answered | answered | support_review_passed | 60.2 |
| RQ-002 | exact | answered | answered | support_review_passed | 60.7 |
| RQ-003 | exact | answered | answered | support_review_passed | 36.5 |
| RQ-004 | exact | answered | answered | support_review_passed | 38.9 |
| RQ-005 | exact | answered | answered | support_review_passed | 77.1 |
| RQ-006 | exact | answered | validation_failed | citation_or_snapshot_invalid | 49.4 |
| RQ-007 | exact | answered | generation_failed | model_timeout | 60.2 |
| RQ-008 | exact | answered | generation_failed | model_timeout | 60.8 |
| RQ-009 | paraphrase | answered | generation_failed | model_timeout | 60.4 |
| RQ-010 | paraphrase | answered | generation_failed | model_timeout | 60.4 |
| RQ-011 | paraphrase | answered | generation_failed | model_timeout | 60.3 |
| RQ-012 | paraphrase | answered | generation_failed | model_timeout | 60.4 |
| RQ-013 | paraphrase | answered | generation_failed | model_timeout | 60.4 |
| RQ-014 | paraphrase | answered | generation_failed | model_timeout | 60.8 |
| RQ-015 | paraphrase | answered | generation_failed | model_timeout | 60.5 |
| RQ-016 | paraphrase | answered | generation_failed | model_timeout | 60.3 |
| RQ-017 | paraphrase | answered | generation_failed | model_timeout | 60.4 |
| RQ-018 | paraphrase | answered | generation_failed | model_timeout | 60.6 |
| RQ-019 | version_conflict | answered | generation_failed | model_timeout | 60.6 |
| RQ-020 | version_conflict | answered | generation_failed | model_timeout | 60.7 |
| RQ-021 | version_conflict | answered | generation_failed | model_timeout | 60.6 |
| RQ-022 | version_conflict | answered | generation_failed | model_timeout | 60.4 |
| RQ-023 | version_conflict | answered | generation_failed | model_timeout | 60.3 |
| RQ-024 | version_conflict | answered | generation_failed | model_timeout | 60.4 |
| RQ-025 | unsupported | insufficient_evidence | generation_failed | model_timeout | 61.5 |
| RQ-026 | unsupported | insufficient_evidence | generation_failed | model_timeout | 60.5 |
| RQ-027 | unsupported | insufficient_evidence | insufficient_evidence | missing_evidence | 55.6 |
| RQ-028 | unsupported | insufficient_evidence | insufficient_evidence | missing_evidence | 52.1 |
| RQ-029 | unsupported | insufficient_evidence | insufficient_evidence | missing_evidence | 49.9 |
| RQ-030 | unrelated | insufficient_evidence | insufficient_evidence | missing_evidence | 52.3 |
| RQ-031 | conflict | conflicting_evidence | generation_failed | model_timeout | 60.3 |
| RQ-032 | partial | insufficient_evidence | insufficient_evidence | missing_evidence | 12.9 |
| RQ-033 | injection | insufficient_evidence | generation_failed | model_timeout | 60.3 |

### Separate application-default 240-second diagnostic subset

This selected subset uses the application configuration without a timeout override. It is separate from the 33-case run and is not pooled into its metrics or claimed to cover all questions at the default budget.

- Attempted answers: 3; statuses: answered=1, insufficient_evidence=1, validation_failed=1.
- Supported-answer status coverage: 1/1 (100.0%).
- Correct explicit abstention: 1/1 (100.0%).
- False-answer frequency on annotated unanswerable cases: 0/1 (0.0%).
- Conflict status: 0/1 (0.0%).
- Returned citation validity: 1/1 (100.0%); missing evidence references: 0.
- Independent human answer support accuracy: **not measured**.

| Case | Expected status | Actual status | Reason | Seconds |
|---|---|---|---|---:|
| RQ-009 | answered | answered | support_review_passed | 72.5 |
| RQ-025 | insufficient_evidence | insufficient_evidence | missing_evidence | 5.7 |
| RQ-031 | conflicting_evidence | validation_failed | citation_or_snapshot_invalid | 74.4 |

## Offline/security evidence and limits

Both real runs used preinstalled dependencies/models under the Python audit guard. Main-run allowed loopback connection count: 1239; blocked external events: 0. Default-budget subset blocked external events: 0. The guard permits only literal loopback connections to the configured Ollama port. A child-process regression verifies actual `connect`, `connect_ex` and external name-resolution rejection.

This is application-level verification, **not an OS air-gap, native-code sandbox or restriction on the separate Ollama server process**. Fixture tests separately deny sockets while exercising ingestion, embedded Chroma, answer mechanics, management and all views. Hostile source text remains data; tested paths expose no shell/tool execution or URL-fetch capability, and an outside-library canary remains unchanged. Model behaviour on the hostile question is recorded above rather than assumed to be safe from a fixture response.

## Release blockers and next milestone

1. PRD section 14 requires at least **30 human-authored questions** and independent human evaluation of semantic answer support. Neither has been supplied or performed. The development questions remain AI-authored and support accuracy remains null. An unfilled exact-output review worksheet is supplied; it is not a completed review.
2. The recorded answer coverage, validation failures, timeout behaviour, abstention and conflict results need quality/performance triage and human acceptance. Passing citation syntax/exact quotes and a second check by the same model are not proof of entailment or completeness. The 60-second run does not establish how every case behaves under 240 seconds.
3. Chroma dependency findings remain unresolved. Resolve, replace or explicitly accept the documented residual risk before claiming release readiness.

Milestone 6 may prepare a portfolio release with these limitations stated, but no validated-release claim follows from milestone 5. Native parser resource limits, logical rather than forensic deletion, protected abandoned staging generations, and prior answer-quality/latency limitations remain. No full user walkthrough or live-library replacement/deletion was performed. The user authorized the first GitHub commit/push after these checks, followed by a pause before milestone 6.

Machine evidence: [knowledgebridge-m5-evaluation.json](evidence/milestone5/knowledgebridge-m5-evaluation.json), [knowledgebridge-m5-default-budget-diagnostics.json](evidence/milestone5/knowledgebridge-m5-default-budget-diagnostics.json), [knowledgebridge-m5-dependency-audit.json](evidence/milestone5/knowledgebridge-m5-dependency-audit.json), and the unfilled [knowledgebridge-m5-human-review-worksheet.json](evidence/milestone5/knowledgebridge-m5-human-review-worksheet.json). Project reproduction and review instructions: `docs/evaluation.md`; acceptance matrix: `docs/acceptance.md`.
