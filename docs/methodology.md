# Extraction and retrieval methodology

TXT/Markdown decode UTF-8 with optional BOM removal and preserve text/line endings. Markdown detects ATX headings outside fenced code, not the full Markdown specification. DOCX extracts body paragraphs and flattened tables in order, using heading/title styles and stripped core-title fallbacks. PDF extracts existing page text in sorted reading order and preserves one-based page numbers. No OCR, URL retrieval or embedded execution occurs.

DOCX comments, tracked changes, headers/footers, images and embedded objects are not fully interpreted. Table layout and PDF reading order may be incomplete. Compare important excerpts against originals.

Passages never cross extracted section/page boundaries. Defaults: up to 500 whitespace-delimited words and 4,000 Unicode characters, with up to 50 overlap words. Paragraph boundaries are preferred; oversized tokens may split with warnings. Defaults are starting choices, not calibrated optimizations. Offsets are half-open Unicode positions into extracted sections. TXT/Markdown also retain BOM-free decoded-text offsets; DOCX/PDF offsets are not original file coordinates. Every passage is validated against its exact section slice.

Document IDs derive from byte hashes. Section IDs include document/version/extraction identity. Passage IDs additionally include chunk settings and offsets. Byte-identical files are duplicates within a collection, even if renamed or assigned another version.

## Embeddings

Ollama `/api/embed` receives bounded batches of raw passage text and raw queries, using the same configured model and no implicit truncation or custom prompt prefixes. Vectors are validated for cardinality, dimensions, finite values and nonzero norm, then normalized. Chroma uses cosine distance. Default model: `embeddinggemma:latest`, verified locally with 768 dimensions. Model digests are checked before and after indexing/query embedding. A changed model requires a rebuild. Missing models, timeouts and malformed vectors return explicit errors; no cloud or keyword fallback is silently substituted.

## Ranking

FTS5 unicode61 tokenization retains underscores (for example `AUTH_REQUIRED` and `session_idle_minutes`). Other punctuation in API paths/flags splits into terms. Queries become at most 64 quoted, deduplicated Unicode terms joined by OR; SQL and user-supplied FTS operators are never executed as syntax. SQLite BM25 ranks candidates, with passage ID breaking ties. Lower BM25 values rank first. This is token-based retrieval, not a substring or exact-path matcher.

Chroma returns cosine-distance candidates. Lower distance ranks first; equal returned distances are ordered by passage ID. Approximate nearest-neighbor selection at the candidate boundary is not guaranteed bit-for-bit stable across platforms. Chroma candidates and keyword candidates are deduplicated and fused as:

`RRF(p) = sum(1 / (k + rank_method(p)))`, with default `k=60` and equal method weights.

Default candidate count is 20 per method and final result count is 5. RRF ties use passage ID. Results preserve exact source passages and individual method ranks/scores. Scores are not calibrated probabilities or proof of relevance. Retrieval can return passages for unsupported questions. Evidence sufficiency and conflicting-answer decisions are not implemented in Milestone 2.

## Development probes

`retrieval_questions.json` contains 30 AI-authored probes: 24 designated source targets and six unsupported/unrelated questions. The reproducible script measures whether at least one designated filename/text target occurs in the top five. It does not measure exhaustive Recall@k, answer support, correct abstention or factual accuracy. Unsupported questions have no success label; their retrieved neighbors must not be interpreted as answers. The independent human-authored benchmark and wider evaluation remain Milestone 5 work.


## Milestone 3 evidence decisions

The answer workflow uses up to 12 hybrid candidates, focuses exact underscore-identifier/flag queries on matching passages plus the top two contextual complements (with broader fallback for no matches), keeps whole-source context bounded by serialized UTF-8 size, schema-constrained claims and exact quoted citations. A separate same-model call checks relevance, entailment, completeness and conflicts; every claimed index must be confirmed. This avoids treating arbitrary cosine or RRF scores as calibrated evidence thresholds. It does not replace human support assessment. Version differences are retained, and source recency alone is not authority. Partial multi-part questions receive abstention when missing details are detected. See milestone_3_design.md and the completion report for actual probes and limitations.


## Milestone 4 lifecycle methodology

Saved library state and active search state are distinct. An imported pending source is persistent but not searchable until activation. Replacement is a complete atomic source/index update; byte hashes detect changed content, while version/chunk settings preserve or invalidate passage identities appropriately. Same-byte metadata/version changes can still require reindexing.

Deletion builds remaining active search data from retained vectors, preserving query/document embedding identity without requiring a model. Empty active libraries have no active index. Retired records are removed after activation; cleanup failures are surfaced without undoing the active deletion. Revision guards prevent concurrent updates from restoring old sources. References to previous generations are conservatively outdated even if a particular passage's text/ID happens to remain unchanged. No claim of secure erasure or perfect model answer support is made.

## Milestone 5 evaluation

See [evaluation methodology](evaluation.md) for exact metric denominators, isolated local-model reproduction, offline verification scope and output-bound human review. The AI-authored development cases do not satisfy the PRD human-authorship requirement. See [acceptance evidence](acceptance.md) for P0 checks and release blockers.
