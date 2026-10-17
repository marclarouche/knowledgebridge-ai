# Walkthrough answer-validation investigation

Investigated October 17, 2026 after the guided FleetOps walkthrough. All reproductions used a separate fictional-only index, the configured local models and application-default request budgets. The existing user/demo library was not rebuilt or changed by these probes. They are targeted development checks, not a full evaluation or human benchmark.

## Reproduced causes

Both original questions returned `validation_failed / citation_or_snapshot_invalid` in isolated reproductions, before reaching support review:

- **Version comparison:** the model selected a valid configuration passage but fabricated a shortened YAML excerpt. It removed intervening `session_idle_minutes` and `api_page_size` lines, then attached the trailing prose. That reconstructed excerpt is not a contiguous source substring. The validator correctly rejected it.
- **PDF-scoped authentication question:** the model quoted the correct PDF text but mistyped characters in its passage UUID. That ID was not in the supplied evidence. The validator correctly rejected it. This was not a failure to retrieve the PDF or preserve its page number.

The original user session's raw draft was not retained; these are observed causes in the isolated reproductions, not a claim to have recovered the original session's unlogged intermediate output.

## Changes

`grounded-5` builds a fresh per-request JSON schema whose evidence passage ID field enumerates only the IDs actually provided in bounded context. This prevents the local schema-constrained decoder from inventing a UUID. Runtime validation still checks every ID and exact source slice, including for other adapters or fixture models; schema compliance alone never establishes support.

Draft instructions explicitly prohibit shortening fenced blocks, joining separated fragments, inserting ellipses or reconstructing a quote. They prefer directly supporting prose or an exact field line without added fences. Draft/review instructions distinguish an explicit comparison of named versions from choosing an authoritative value for an unspecified deployment, preserving new-versus-existing workspace qualifications.

Safe citation diagnostics now distinguish `citation_outside_context`, `citation_quote_mismatch`, `citation_source_mismatch`, `snapshot_changed` and `conflict_sources_not_distinct`. The interface gives a corresponding explanation without showing rejected claims or raw drafts. A separate `support_incomplete` explanation states that the review could not confirm a complete, relevant response; it does not claim that the manuals necessarily omit the fact. Historical `grounded-4` answers and historical evaluation records remain readable.

No fuzzy matching, automatic ID correction, quote rewriting, dropped evidence references, bypassed support review or extra retry calls were added. A malformed quote still causes withholding. Model output remains fallible.

## Verification

All **140 tests passed**, with five upstream SWIG deprecation warnings. Ruff lint/formatting and strict mypy (19 source files) passed. Installed requirements are consistent. New/extended regression checks cover context-only schema enums, isolation of schemas across requests, noncontiguous YAML rejection, valid exact field quotes, safe failure reasons and historical prompt-version loading. Existing stale snapshot, hostile input, missing-source, independent review and offline UI tests remain passing.

The required pip-audit still reports five entries in Chroma 1.5.9 (four unique advisories, no fixed versions listed). No dependencies or configured model/request budgets changed. Original release blockers remain open; historical Phase 5 metrics are unchanged.

## Import and management walkthrough

[Disposable practice documents](../samples/library_walkthrough/README.md) are separate from the evaluated FleetOps corpus. A temporary-index smoke check with controlled embeddings verified importing version 1.0, indexing, replacing it with version 2.0, removing the old unique keyword from active search, rejecting the old generation reference, and deleting the last document without a model. It did not mutate any live collection. These fixtures validate mechanics, not model quality.

## Follow-up local-model results

A first follow-up with constrained passage IDs returned a supported PDF answer, but the comparison still shortened a YAML quote. The final instructions additionally clarify version-scoped comparisons and prefer supporting prose. The final targeted run passed the comparison through exact citation validation; its draft nevertheless misclassified the version distinction as a conflict and its review rejected relevance/completeness. It remains withheld with reason `support_incomplete`, rather than being declared fixed. This is now a semantic drafting/review limitation, not the original mistyped-ID or noncontiguous-quote failure in that run.

| Question | Baseline | Final targeted result | End-to-end seconds |
|---|---|---|---:|
| Default require_mfa in 1.0 versus 2.0 | Citation validation failed | Withheld: support_incomplete | 118.5 |
| AUTH_REQUIRED according to Troubleshooting Guide | Citation validation failed | Answered, support_review_passed; exact page-2 PDF citation | 48.1 |
| Recovery-code regeneration (unsupported control) | Not rerun as a baseline | Withheld: support_incomplete | 149.2 |

The PDF answer states that the API request did not include a valid workspace token. That successful single retest is not an overall quality guarantee. The comparison should still be checked in the sources or split into version-specific questions. Raw fictional-only probe traces are kept in Git-ignored `outputs/walkthrough-investigation-before.json`, `outputs/walkthrough-investigation-after.json` and `outputs/walkthrough-investigation-final.json`. The final trace records the prompts, schemas, supplied context, draft and review; no normal-library documents or user-session drafts were captured.

The unsupported control returned no instructions or citations to the user, but its draft incorrectly labeled two statements of missing information as a conflict. Review withheld it with `support_incomplete`. This is not a clean direct missing-evidence decision; conflict/status selection remains an open model-quality issue. The final specific support-review message was verified by the 31-test answering-suite rerun after the live probes started. No stronger claim of improved semantic quality follows from the citation fix.

A compact [follow-up evidence summary](evidence/walkthrough/walkthrough-followup.json) records final statuses, returned citations and model identity. The summary does not contain rejected drafts or relabel these development probes as a human benchmark.

## Completed user walkthrough

After the investigation, the user observed successful import/index/search of the disposable version-1 guide, replacement by version 2 with the corrected title/version and new verification label, no keyword matches for the old label, and deletion leaving zero documents/passages and no active generation. The user then returned to FleetOps Demo. These are user-reported UI observations; the separate temporary-index smoke check above supplies automated lifecycle evidence.
