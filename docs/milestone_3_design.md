# Milestone 3 answer policy

The answer path uses hybrid retrieval over the last active saved collection. It expands the answer candidate window to at most 12 passages by default and retains complete passages within an 18,000-byte serialized-source budget. For questions containing exact underscore identifiers or command flags, matching passages plus the top two contextual complements are retained; paraphrases/no-match queries keep the broader candidate set. This provisional context-selection heuristic can omit supporting or conflicting passages and is not a sufficiency test. Unlike search, the answer path does not interpret a nearest-neighbor score as evidence sufficiency. There is no uncalibrated numeric confidence threshold. Irrelevance, missing details and conflicts are assessed in a structured draft and a separate support-review call.

Question and sources are JSON data in a user message; fixed policy is a separate system message. Ollama receives no tool definitions, images, history, filesystem paths, source-derived commands or external URLs to execute. A local model draft may contain only supported claims with exact source quotes, an empty insufficient-evidence result, or conflict pairs citing distinct passages. Model prose is never displayed before application validation.

Citation validation resolves each passage ID in the supplied retrieval context AND current saved collection, compares the full passage and source hash, and requires an exact nonblank contiguous quote. Quote offsets are half-open positions within the passage (add its section char_start for section-relative positions). Missing, stale, out-of-context and fabricated citations fail closed. Final successful answers recheck active generation after the support-review call; an intervening rebuild invalidates the draft.

A second call, with a separate review instruction and no prior chat history, assesses whether cited quotes actually entail each claim, whether all requested details are covered, whether the evidence is relevant, and whether applicable disagreements remain unresolved. It must explicitly confirm all claim or conflict indexes. Definitive answers additionally require complete direct coverage of the question. A confirmed relevant conflict can be shown as a warning even though it cannot establish a definitive requested value. Safe review booleans and indexes are included in diagnostics. This is a separate call to the same configured model, NOT an independent human assessment or independent model. Correlated errors and prompt injection remain possible. Exact quotes and valid IDs alone do not establish factual correctness. Human review remains required.

## Status policy

- `answered`: every claim has valid exact citations and passes support/completeness/conflict review.
- `insufficient_evidence`: no bounded source context, an explicit model abstention, irrelevant evidence or incomplete requested details. Partial definitive answers are withheld.
- `conflicting_evidence`: two or more distinct source passages support an unresolved issue, confirmed by review. Both quotes/versions are shown; no authority is inferred solely from version recency.
- `validation_failed`: malformed structured output, invalid/stale citations, unsupported claims, invalid review indexes, or an unconfirmed/hidden conflict. The raw draft is discarded.
- `generation_failed`: local retrieval/model availability failure, changed generation-model identity, timeout, incomplete/token-limited response or context-budget failure. The index is unchanged.

Model identity, prompt-policy version, active index generation, context count, omitted-passage count, elapsed time and safe reason codes appear in diagnostics. No full question, prompt, response or source text is logged. The app displays a single request's answer during that rerun; there is no persisted answer history. As with any local UI, browser/process memory can retain displayed text.

## Runtime budgets

Generation uses the existing loopback-only, bounded, no-proxy/no-redirect transport. Installed models are verified by local catalog digest and cloud-backed metadata is rejected. The app never automatically pulls a generation model. Default `qwen3-vl:4b-instruct` was already installed. Generation and review use JSON schemas, temperature 0, seed 0, a configurable context window, maximum generated tokens and socket timeout (240 seconds by default on the verified CPU-only setup). Token-limited/incomplete responses are rejected. A conservative UTF-8 byte budget reserves output tokens and template overhead before a request; it can reject requests that a tokenizer might otherwise fit. Context passages are skipped whole when oversized, never clipped into misleading excerpts. Retrieval remains available if generation is unavailable.

## Remaining limitations

The finite retrieval window can miss relevant evidence or a conflicting source. The model can incorrectly endorse a claim or abstain unnecessarily. Conflict detection applies only to retrieved source scope. No threshold is claimed calibrated, and no accuracy, immunity to prompt injection or factual-verification guarantee is made. Human-authored independent evaluation remains Milestone 5 work. Existing Chroma advisories and embedded-only applicability assessment remain in security.md. Deletion, replacement, persistent answers and export are not part of this milestone.

Upstream API references: [Ollama chat API](https://docs.ollama.com/api/chat), [structured output schemas](https://docs.ollama.com/capabilities/structured-outputs).
