# KnowledgeBridge AI: making technical answers inspectable

## The documentation problem

A support question can span an API reference, an administrator guide and an older configuration manual. Keyword search helps with exact codes but can miss paraphrases. A general language model can produce fluent instructions without evidence. KnowledgeBridge AI explores how a technical-document collection can support local search and answers whose quoted sources remain inspectable.

The intended audience is technical writers, documentation managers and support staff working with curated manuals. The portfolio uses eight original fictional FleetOps documents across Markdown, TXT, DOCX and PDF. Intentional version differences, missing procedures and inert hostile instructions make limitations observable without exposing private source material.

## Design and implementation

The project connects information architecture to evidence handling: document, section and passage identities preserve version/page/offset information through extraction, chunking, retrieval and answer display. Streamlit owns presentation; typed Python modules own processing. SQLite FTS5 supplies exact-term candidates, local Ollama embeddings supply semantic candidates, and reciprocal rank fusion combines their ranks without presenting scores as confidence probabilities.

A cited answer must quote an exact current passage. A separate call to the same local generation model reviews support and completeness before substantive output is returned. These gates can withhold invalid drafts, but they cannot independently establish truth or complete entailment. Source Explorer exposes the supporting context so a person can inspect it.

Lifecycle behavior is part of citation quality. Pending imports are durable but separate from the active index. Replacement stages a new snapshot before atomic activation. Deletion reuses retained vectors without requiring a running model. Revision checks reject stale writes, and obsolete references are withheld after replacement or deletion. This avoids quietly treating an old citation as current evidence. Logical deletion remains distinct from secure erasure.

## Technical writing deliverables

The [installation guide](installation.md) provides locked setup and troubleshooting; the [user guide](user_guide.md) follows the collection-to-source workflow. The [architecture diagram](architecture.md#system-diagram) shows storage and model boundaries. [Methodology](methodology.md) explains extraction offsets, ranking, version treatment and evaluation denominators. The [evaluation report](evaluation_report.md) and [recorded examples](sample_answers.md) retain failures alongside successful answers. [Screenshots](screenshots/README.md) document the actual fictional-demo interface.

## What the evidence shows

All 136 software tests passed, including offline fixtures, stale references and lifecycle failures. Semantic retrieval found the annotated top-five targets in all 26 targeted development cases; keyword and hybrid each missed one. Those AI-authored targets are neither an exhaustive relevance benchmark nor a measure of answer correctness.

The 33-case answer run returned five answered outputs, five explicit abstentions, one validation failure and 22 generation failures under its 60-second request budget. Returned citations passed exact-reference checks, while independent semantic support was not measured. The live conflict probe failed to return a conflict status, including in a separate default-budget diagnostic. These results exposed availability, conflict handling and latency as unresolved product issues rather than supporting a blanket accuracy claim.

## Tradeoffs and next work

Local models avoid a cloud inference dependency after setup, but CPU latency can undermine the experience. Exact citations improve traceability but do not prove entailment. Atomic active snapshots protect the visible library while separate Chroma and SQLite stores still permit abandoned staging data. Bounded parsing reduces input exposure without providing a native-parser sandbox.

The current outcome is a reproducible development/portfolio application with explicit release blockers. Before a validated release, obtain at least 30 human-authored questions and independent support review, triage model quality and performance against user expectations, and resolve or explicitly accept the documented dependency risk. No production deployment, human benchmark pass, measured business impact or external user adoption is claimed.
