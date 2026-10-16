"""Document reindexing keeps the active generation unchanged until full success."""

from knowledgebridge.chunker import chunk_sections
from knowledgebridge.config import Settings
from knowledgebridge.embedding_adapter import Embedder
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.models import KnowledgeCollection
from knowledgebridge.retrieval_models import IndexManifest, RetrievalError


def reindex_document(
    repository: IndexRepository,
    collection_id: str,
    document_id: str,
    settings: Settings,
    embedder: Embedder,
    *,
    expected_revision: int | None = None,
) -> IndexManifest:
    """Rechunk one retained document, then atomically rebuild its collection snapshot."""
    collection, _ = repository.load(collection_id)
    library, revision = repository.library_entry(collection_id)
    if expected_revision is not None and expected_revision != revision:
        raise RetrievalError("Collection changed. Reload before reindexing.")
    document = next((d for d in collection.documents if d.document_id == document_id), None)
    if document is None:
        raise RetrievalError("Document is not in the saved collection.")
    try:
        document.passages = chunk_sections(
            document.sections, settings.chunking, max_passages=settings.max_passages_per_document
        )
    except ValueError:
        raise RetrievalError(
            "Rechunking exceeds passage limits; the active index is unchanged."
        ) from None
    collection = KnowledgeCollection.model_validate_json(collection.model_dump_json())
    if sum(len(d.passages) for d in collection.documents) > settings.max_collection_passages:
        raise RetrievalError("Rechunking exceeds collection passage limits.")
    for current in library.documents:
        if current.document_id == document_id:
            current.passages = document.passages
    return repository.build(
        collection, embedder, settings.retrieval, expected_revision=revision, library_source=library
    )
