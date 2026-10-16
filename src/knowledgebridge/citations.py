"""Resolve cited exact quotes only against the active snapshot and supplied context."""

from knowledgebridge.answer_models import Citation, DraftAnswer
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.retrieval_models import RetrievalError, RetrievalHit


class CitationValidationError(RetrievalError):
    """Invalid active-source evidence; safe abstention without a raw draft."""


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
            "The saved index changed. Ask again against the current sources."
        )
    active = {p.passage_id: (d, p) for d in collection.documents for p in d.passages}
    allowed = {h.passage.passage_id: h for h in context}
    citations: dict[tuple[str, str], Citation] = {}
    groups = [c.evidence for c in draft.claims] + [c.evidence for c in draft.conflicts]
    for evidence in groups:
        for ref in evidence:
            hit = allowed.get(ref.passage_id)
            source = active.get(ref.passage_id)
            if (
                hit is None
                or source is None
                or source[1] != hit.passage
                or source[0].content_hash != hit.content_hash
                or not ref.quote.strip()
                or ref.quote not in source[1].text
            ):
                raise CitationValidationError(
                    "A citation is missing, stale or does not match an exact source quote."
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
                "A conflict must cite at least two different source passages."
            )
    return list(citations.values())
