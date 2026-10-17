"""Resolve cited exact quotes only against the active snapshot and supplied context."""

from typing import Literal

from knowledgebridge.answer_models import Citation, DraftAnswer
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.retrieval_models import RetrievalError, RetrievalHit


class CitationValidationError(RetrievalError):
    """Invalid active-source evidence; safe abstention without a raw draft."""

    def __init__(
        self,
        message: str,
        *,
        reason: Literal[
            "citation_or_snapshot_invalid",
            "snapshot_changed",
            "citation_outside_context",
            "citation_source_mismatch",
            "citation_quote_mismatch",
            "conflict_sources_not_distinct",
        ] = "citation_or_snapshot_invalid",
    ) -> None:
        super().__init__(message)
        self.reason = reason


def validate_citations(
    repository: IndexRepository,
    collection_id: str,
    generation: str,
    context: list[RetrievalHit],
    draft: DraftAnswer,
) -> list[Citation]:
    collection, manifest = repository.load(collection_id)
    if manifest.generation != generation:
        raise CitationValidationError(
            "The saved index changed. Ask again against the current sources.",
            reason="snapshot_changed",
        )
    active = {p.passage_id: (d, p) for d in collection.documents for p in d.passages}
    allowed = {h.passage.passage_id: h for h in context}
    citations: dict[tuple[str, str], Citation] = {}
    groups = [c.evidence for c in draft.claims] + [c.evidence for c in draft.conflicts]
    for evidence in groups:
        for ref in evidence:
            hit = allowed.get(ref.passage_id)
            source = active.get(ref.passage_id)
            if hit is None or source is None:
                raise CitationValidationError(
                    "A cited passage was not supplied as current evidence.",
                    reason="citation_outside_context",
                )
            if source[1] != hit.passage or source[0].content_hash != hit.content_hash:
                raise CitationValidationError(
                    "A citation does not match the current source record.",
                    reason="citation_source_mismatch",
                )
            if not ref.quote.strip() or ref.quote not in source[1].text:
                raise CitationValidationError(
                    "A draft quote is not an exact contiguous source excerpt.",
                    reason="citation_quote_mismatch",
                )
            document, passage = source
            start = passage.text.index(ref.quote)
            citations[(ref.passage_id, ref.quote)] = Citation(
                passage=passage,
                title=document.title,
                filename=document.filename,
                content_hash=document.content_hash,
                quote=ref.quote,
                quote_start=start,
                quote_end=start + len(ref.quote),
            )
    for conflict in draft.conflicts:
        if len({ref.passage_id for ref in conflict.evidence}) < 2:
            raise CitationValidationError(
                "A conflict must cite at least two different source passages.",
                reason="conflict_sources_not_distinct",
            )
    return list(citations.values())
