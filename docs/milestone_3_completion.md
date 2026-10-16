# KnowledgeBridge AI — Milestone 3 completion

Project: /Users/cyberlifecoach/Projects/knowledgebridge-ai. Verified October 16, 2026.

## Implementation

Milestone 3 adds local structured generation through the installed qwen3-vl:4b-instruct model, exact active-source citation validation, a separate model support review, insufficient-evidence handling and conflicting-source responses. The new Ask KnowledgeBridge view displays claim references, exact source quotes, version/section/page metadata, full source passages and safe diagnostics. No library deletion/replacement, answer history, export workflow or later milestone feature was added.

New engine modules: answer_models.py, answer_generator.py, citations.py and answering.py. Updated embedding_adapter.py to share its bounded loopback-only transport with generation; config.py and YAML add generation budgets. New tests/test_answering.py covers orchestration/security/failure cases. scripts/evaluate_answers.py exercises only the fictional FleetOps Demo. Updated app.py, AGENTS.md, README and architecture/security/methodology/user-guide documentation; docs/milestone_3_design.md specifies policy and limits. Original supplied PRD/technology notes and saved index data are preserved.

The core package remains independent of Streamlit. No new dependency or generation-model download was required. Generation uses the already installed qwen3-vl:4b-instruct; embeddings still use embeddinggemma:latest. Requests go only to the configured loopback Ollama service, without proxies, redirects, model tools, implicit pulls or cloud fallbacks. Source/question text is untrusted JSON beneath fixed system policy. Structured drafts are never displayed before validation.

Each substantive claim needs an exact nonblank source quote. IDs must resolve both in the supplied retrieved context and active saved collection, and full passage/source-hash identity must agree. A separate call checks relevance, claim entailment, completeness and conflicts. Final substantive results recheck snapshot freshness. Uncertain, partial, malformed or unsupported drafts are withheld. Unresolved confirmed conflicts show distinct source quotations and a request for human verification, without choosing authority from version recency.

## Verification

- Actual-project pytest: 99 passed; five upstream SWIG deprecation warnings. Final full run: 11.85 seconds.
- Ruff lint and formatting passed; 43 files checked.
- Strict mypy passed across 16 source files.
- pip check: no broken requirements. pip emitted a sandbox cache warning, then completed successfully.
- uv sync --locked --group dev passed with the existing 135-package lock resolution; no dependency changes were needed.
- Offline controlled-model tests passed for answer UI, exact quote resolution, unsupported/partial evidence, duplicate/negative review indexes, stale references during draft/review, model failure/change, malformed outputs, output token/context limits and preservation of saved indexes.

## Security audit

The refreshed pip-audit still returns five findings representing the same four unique Chroma 1.5.9 advisories, with no listed fixed version. PYSEC-2026-311 appears twice. No finding is suppressed; the unpublished local package is skipped because it is absent from PyPI. The embedded-only applicability assessment from Milestone 2 remains: this app exposes no Chroma HTTP server, server RBAC or user-configurable remote embedding repositories. The audit is not clean. Details and upstream links are in docs/security.md; raw results are supplied alongside this report.

## Limitations

The second review is another call to the same model, not an independent human or independently trained verifier. Correlated model errors, missed conflicts, prompt injection and unsupported answers remain possible. Citation validity and exact quotes do not prove factual correctness or source authority. Important answers require human review. A finite retrieval/context window can omit relevant or conflicting sources; whole passages exceeding the byte budget are omitted with a diagnostic count. No calibrated confidence scores or independent accuracy claims are made.

CPU-only generation is slow and includes two sequential calls for a substantive answer. Socket timeouts, output tokens, input byte budget and response size are bounded; failures withhold drafts and preserve indexes. Questions/answers/prompts are not logged or persisted as application history, though browser/process memory and the separately operated local Ollama service are outside secure-erasure guarantees. Old index generations remain on disk as documented in Milestone 2.


## Actual real-model probes

The final development probe uses the saved eight-manual, 31-passage fictional FleetOps collection with embeddinggemma:latest and qwen3-vl:4b-instruct. Generation digest: ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b. Questions were authored by AI, not independently human-authored or graded. No answer-support accuracy or production-readiness percentage is claimed.

| Case | Question type | Expected | Actual | Seconds |
| --- | --- | --- | --- | --- |
| 0 | supported | answered | validation_failed | 40.6 |
| 1 | supported | answered | answered | 55.6 |
| 2 | unsupported | insufficient_evidence | insufficient_evidence | 56.2 |
| 3 | unsupported | insufficient_evidence | insufficient_evidence | 52.5 |
| 4 | partial | insufficient_evidence | insufficient_evidence | 15.7 |
| 5 | conflict | conflicting_evidence | conflicting_evidence | 110.1 |
| 6 | version_scope | answered | validation_failed | 90.9 |
| 7 | unrelated | insufficient_evidence | insufficient_evidence | 34.8 |
| 8 | injection | insufficient_evidence | validation_failed | 76.1 |

The page-size answer stated that the maximum is 100 and cited the exact source sentence. Missing audit retention and TLS details, partial token-rotation support and unrelated weather questions produced abstentions. Authentication and version-specific questions were withheld because model-generated citations failed exact active-source validation. The hostile FAQ request also produced a citation-validation failure and displayed no generated instructions; no command or URL was executed. Those failures are safe withholding, not evidence of good answer quality.

The real conflict recheck displayed exact quotations establishing a 30-minute current default versus a 60-minute legacy default, with separate source versions and no definitive deployment value. Its support-review flags confirmed both reported disagreements; the lack of a definitive value was kept distinct from a relevant conflict warning. A conflict warning requires exact citations from distinct passages, relevant evidence, confirmation of every conflict and an unresolved disagreement; it does not require resolving the definitive requested value. Definitive answers still require direct complete coverage and confirmation of every claim.

The exact-identifier context heuristic keeps matching underscore identifiers/command flags plus the two highest-ranked complements; no-match/paraphrase queries keep the wider set. This can omit evidence and is not a calibrated relevance guarantee. Whole passages remain bounded by serialized UTF-8 size.

The initial 120-second budget timed out on complex CPU requests. Default generation socket timeout is now 240 seconds per request, with a safe model_timeout diagnostic; two sequential calls can still be slow. Preliminary tests exposed over-abstention and a referral-style answer that did not state a requested fact directly; the policy now requires direct fact coverage. The same-model review remains fallible and human review is still required.

## Run and inspect

```sh
uv sync --locked --group dev
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Use Ask KnowledgeBridge against a saved index. Ollama and both configured local models must be available. The app was left running on port 8502; the other application on port 8501 was not stopped. No Git commit, remote setup or push was performed.

The new answer path is implemented with traceable answers and explicit withholding on detected failures. This is a development milestone, not a production release or independent evaluation. Model answer coverage/citation copying, latency, prompt-injection robustness and the Chroma advisories remain release limitations to address during evaluation. Milestone 4 has not started.

## Live browser verification

The final running application successfully answered “What is the maximum page_size for GET /v2/work-orders?” with “The maximum page_size for GET /v2/work-orders is 100.” It displayed the exact source quote “The maximum page_size is 100.” from FleetOps API Reference version 2.0, section Read work orders, passage ebd37191-81ce-561b-87c1-49605e24415a. Source details and full passage inspection were available. A screenshot accompanies this report. The server is still running on 127.0.0.1:8502.
