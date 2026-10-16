"""Explicit embedding identity and source-preserving retrieval records."""

from typing import Literal

from pydantic import Field

from knowledgebridge.models import DocumentPassage, Record


class RetrievalError(ValueError):
    """Safe application message, never raw source or server response text."""


class EmbeddingIdentity(Record):
    model: str = Field(min_length=1, max_length=200)
    digest: str = Field(min_length=1, max_length=200)
    dimensions: int = Field(ge=1, le=8192)
    adapter_version: Literal["ollama-embed-1"] = "ollama-embed-1"
    truncate: Literal[False] = False


class IndexManifest(Record):
    collection_id: str
    generation: str
    identity: EmbeddingIdentity
    passage_count: int = Field(ge=1)
    source_fingerprint: str
    indexed_at: str


class RetrievalHit(Record):
    passage: DocumentPassage
    title: str
    filename: str
    content_hash: str
    rank: int
    methods: list[str]
    keyword_rank: int | None = None
    semantic_rank: int | None = None
    bm25: float | None = None
    cosine_distance: float | None = None
    rrf_score: float | None = None


class RetrievalReport(Record):
    mode: Literal["keyword", "semantic", "hybrid"]
    generation: str
    hits: list[RetrievalHit]
    candidate_count: int
    rrf_k: int
    elapsed_ms: float
    warnings: list[str] = Field(default_factory=list)
