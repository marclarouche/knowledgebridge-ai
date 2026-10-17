# Evaluation report

Recorded October 16, 2026; software checks refreshed October 17. This is development evidence from fictional documents and AI-authored questions. It does not satisfy the PRD's human-authored benchmark requirement. Full outputs, settings, source hashes and model digests are in [Milestone 5 evidence](milestone_5_completion.md).

## Scope and results

Eight fictional manuals produced 31 passages. Retrieval used 33 development cases, of which 26 had annotated passage targets; seven untargeted cases are excluded from recall. Annotations are not exhaustive human relevance judgments.

| Retrieval mode | Macro annotated passage Recall@5 | Target hit rate@5 |
|---|---:|---:|
| Keyword | 96.2% | 96.2% |
| Semantic | 100.0% | 100.0% |
| Hybrid | 96.2% | 96.2% |

Keyword and hybrid missed the legacy MFA target, RQ-019. Retrieval relevance alone does not establish an answer's support.

The 33-case answer run used `qwen3-vl:4b-instruct` with an explicit 60-second limit per generation request. The app default is 240 seconds per request. Retrieval, drafting and review are separate operations; the limit is not an end-to-end budget.

| Measurement | Observed result |
|---|---|
| Statuses | 5 answered; 1 validation failure; 22 generation failures; 5 insufficient evidence |
| Answered status on answerable cases | 5/24 (20.8%) |
| Correct explicit abstention | 5/8 (62.5%) |
| False answered status on unanswerable cases | 0/8 |
| Conflict status | 0/1 |
| Valid returned citations | 7/7; no missing evidence references |
| Independent human support accuracy | Not measured |
| End-to-end median | 60.4 seconds; range 12.9–77.1 seconds |

Citation validity is conditioned on returned outputs that passed the application's validators. Rejected drafts and failures remain visible in status counts. Zero false answers with many failures is not evidence of good availability or robust abstention.

A separate three-case diagnostic subset used the 240-second default: one answered, one insufficient evidence, one validation failure on the conflict question. That selected subset is not pooled with the main run and does not establish full default-budget behavior.

## Software and offline verification

All 136 tests passed on October 17, including parser boundaries, lifecycle rollback/staleness, citations, evaluation scoring, hostile input, offline guards and all nine Streamlit views. Ruff and strict mypy passed. No broken installed requirements were found. Fixture models verify mechanics, not semantic answer quality.

Real-model development runs recorded no blocked external events under a Python audit guard allowing only the configured loopback Ollama port. Fixture tests deny sockets. This is application-level evidence, not an OS air-gap or a restriction on the separate Ollama server/native libraries.

The fresh dependency audit still reports five entries/four unique Chroma advisories with no fixed versions listed. Embedded-only operation and explicit vectors narrow the recorded server/configuration exposure; they do not make the audit clean.

## Release decision and next evidence

The portfolio demonstrates implemented retrieval, source inspection, lifecycle controls and evaluation tooling. Validated release remains blocked by missing human-authored questions/independent support review, unresolved model behavior and latency, and dependency findings. Do not present fixture passes, exact quote matching or same-model review as proof of factual support.

Follow [the reproduction and human-review workflow](evaluation.md) and [acceptance matrix](acceptance.md). The [sample outputs](sample_answers.md) include successful, withheld and failed cases from the recorded run.
