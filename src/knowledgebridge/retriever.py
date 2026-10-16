"""Deterministic rank fusion; returns evidence passages, never generated answers."""

from time import monotonic

from knowledgebridge.config import RetrievalSettings
from knowledgebridge.embedding_adapter import Embedder
from knowledgebridge.index_repository import IndexRepository, SearchMode
from knowledgebridge.retrieval_models import RetrievalError, RetrievalHit, RetrievalReport


def fuse(keyword: list[str], semantic: list[str], k: int) -> list[tuple[str, float]]:
    """Equal-weight reciprocal rank fusion; stable passage ID resolves ties."""
    scores: dict[str, float] = {}
    for ranking in (keyword, semantic):
        for rank, passage_id in enumerate(dict.fromkeys(ranking), 1):
            scores[passage_id] = scores.get(passage_id, 0.0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def retrieve(
    repository: IndexRepository,
    collection_id: str,
    query: str,
    mode: SearchMode,
    settings: RetrievalSettings,
    embedder: Embedder | None = None,
) -> RetrievalReport:
    """Require explicit semantic availability; no silent fallback or confidence claims."""
    started = monotonic()
    if mode not in ("keyword", "semantic", "hybrid"):
        raise RetrievalError("Choose keyword, semantic or hybrid retrieval.")
    if not query.strip() or len(query) > settings.max_query_chars:
        raise RetrievalError("Enter a nonblank query within the configured character limit.")
    collection, manifest = repository.load(collection_id)
    keyword = (
        repository.keyword(manifest, query, settings.candidate_count) if mode != "semantic" else []
    )
    semantic: list[tuple[str, float]] = []
    if mode != "keyword":
        if embedder is None:
            raise RetrievalError("Semantic retrieval requires the local embedding model.")
        identity = embedder.identity()
        if identity != manifest.identity or identity.model != settings.model:
            raise RetrievalError(
                "Embedding model/configuration changed. Rebuild the index before semantic search."
            )
        embedding = embedder.embed([query])[0]
        if embedder.identity() != identity:
            raise RetrievalError("Embedding model changed during query. Retry after rebuilding.")
        semantic = repository.semantic(collection, manifest, embedding, settings.candidate_count)
    kw = {pid: (i, score) for i, (pid, score) in enumerate(keyword, 1)}
    sem = {pid: (i, score) for i, (pid, score) in enumerate(semantic, 1)}
    if mode == "hybrid":
        ranking = fuse(list(kw), list(sem), settings.rrf_k)
    else:
        ranking = [(pid, 0.0) for pid, _ in (keyword if mode == "keyword" else semantic)]
    sources = {p.passage_id: (d, p) for d in collection.documents for p in d.passages}
    hits = []
    for rank, (pid, score) in enumerate(ranking[: settings.top_k], 1):
        if pid not in sources:
            raise RetrievalError("Retrieved source is stale or missing. Rebuild the index.")
        document, passage = sources[pid]
        hits.append(
            RetrievalHit(
                passage=passage,
                title=document.title,
                filename=document.filename,
                content_hash=document.content_hash,
                rank=rank,
                methods=(["keyword"] if pid in kw else []) + (["semantic"] if pid in sem else []),
                keyword_rank=kw[pid][0] if pid in kw else None,
                semantic_rank=sem[pid][0] if pid in sem else None,
                bm25=kw[pid][1] if pid in kw else None,
                cosine_distance=sem[pid][1] if pid in sem else None,
                rrf_score=score if mode == "hybrid" else None,
            )
        )
    _, current = repository.load(collection_id)
    if current.generation != manifest.generation:
        raise RetrievalError(
            "The active index changed during retrieval. Retry against current sources."
        )
    return RetrievalReport(
        mode=mode,
        generation=manifest.generation,
        hits=hits,
        candidate_count=settings.candidate_count,
        rrf_k=settings.rrf_k,
        elapsed_ms=round((monotonic() - started) * 1000, 2),
        warnings=[
            "Ranking scores are not confidence probabilities. Similar passages may not answer the question."
        ],
    )
