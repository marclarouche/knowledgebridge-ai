"""Transactional document lifecycle, collection management and active source inspection."""

from collections.abc import Iterable

import numpy as np
from pydantic import Field

from knowledgebridge.answer_models import Citation
from knowledgebridge.config import Settings
from knowledgebridge.embedding_adapter import Embedder, validate_vectors
from knowledgebridge.index_repository import IndexRepository, fingerprint
from knowledgebridge.ingestion import import_document
from knowledgebridge.models import KnowledgeCollection, Record, now
from knowledgebridge.retrieval_models import RetrievalError


class LibraryResult(Record):
    changed: bool
    collection_id: str
    warnings: list[str] = Field(default_factory=list)


class LibraryStatus(Record):
    status: str
    documents: int
    indexed_documents: int = 0
    indexed_passages: int = 0
    generation: str | None = None
    detail: str


class LibraryManager:
    def __init__(self, repository: IndexRepository):
        self.repository = repository

    def _entry(self, collection_id: str, expected_revision: int) -> KnowledgeCollection:
        source, revision = self.repository.library_entry(collection_id)
        if revision != expected_revision:
            raise RetrievalError("Collection changed. Reload before updating it.")
        return source

    def create(self, title: str) -> KnowledgeCollection:
        try:
            source = KnowledgeCollection(title=title.strip())
        except ValueError:
            raise RetrievalError(
                "Enter a nonblank collection title of at most 500 characters."
            ) from None
        self.repository.save_library(source)
        return source

    def index(
        self, collection_id: str, settings: Settings, embedder: Embedder, expected_revision: int
    ) -> LibraryResult:
        source = self._entry(collection_id, expected_revision)
        self.repository.build(
            source, embedder, settings.retrieval, expected_revision=expected_revision
        )
        return LibraryResult(
            changed=True, collection_id=collection_id, warnings=self.repository.cleanup()
        )

    def replace_document(
        self,
        collection_id: str,
        document_id: str,
        data: bytes,
        filename: str,
        settings: Settings,
        embedder: Embedder | None,
        expected_revision: int,
        *,
        version: str = "unspecified",
        title: str | None = None,
        category: str | None = None,
    ) -> LibraryResult:
        source = self._entry(collection_id, expected_revision)
        old = next((d for d in source.documents if d.document_id == document_id), None)
        if old is None:
            raise RetrievalError("The selected document is no longer in this collection.")
        remaining = source.model_copy(deep=True)
        remaining.documents = [d for d in remaining.documents if d.document_id != document_id]
        parsed = import_document(
            data,
            filename,
            settings,
            existing=remaining,
            version=version,
            title=title,
            category=category,
        )
        if parsed.document is None:
            raise RetrievalError(
                "Replacement rejected. " + " ".join(w.message for w in parsed.warnings)
            )
        replacement = parsed.document
        if (
            replacement.content_hash == old.content_hash
            and replacement.version == old.version
            and replacement.title == old.title
            and replacement.filename == old.filename
            and replacement.category == old.category
        ):
            return LibraryResult(
                changed=False,
                collection_id=collection_id,
                warnings=["Identical bytes and metadata; the saved document is unchanged."],
            )
        source.documents = [
            replacement if d.document_id == document_id else d for d in source.documents
        ]
        source.modified_at = now()
        source = KnowledgeCollection.model_validate_json(source.model_dump_json())
        indexed = self.repository.active_generation(collection_id) is not None
        if indexed:
            if embedder is None:
                raise RetrievalError(
                    "Replacing an indexed source requires the local embedding model."
                )
            self.repository.build(
                source, embedder, settings.retrieval, expected_revision=expected_revision
            )
        else:
            self.repository.save_library(source, expected_revision)
        return LibraryResult(
            changed=True,
            collection_id=collection_id,
            warnings=[w.message for w in parsed.warnings] + self.repository.cleanup(),
        )

    def delete_document(
        self, collection_id: str, document_id: str, expected_revision: int
    ) -> LibraryResult:
        source = self._entry(collection_id, expected_revision)
        if not any(d.document_id == document_id for d in source.documents):
            raise RetrievalError("The selected document is no longer in this collection.")
        source.documents = [d for d in source.documents if d.document_id != document_id]
        source.modified_at = now()
        active_pair = (
            self.repository.load(collection_id)
            if self.repository.active_generation(collection_id) is not None
            else None
        )
        if active_pair is None:
            self.repository.save_library(source, expected_revision)
        else:
            active, manifest = active_pair
            if not any(d.document_id == document_id for d in active.documents):
                self.repository.save_library(source, expected_revision)
            else:
                active.documents = [d for d in active.documents if d.document_id != document_id]
                active.modified_at = now()
                if not active.documents:
                    self.repository.deactivate(collection_id, source, expected_revision)
                else:
                    vector = self.repository.vectors(
                        self.repository.load(collection_id)[0], manifest
                    )
                    passages = [p for d in active.documents for p in d.passages]

                    def batches() -> Iterable[tuple[list[str], list[list[float]]]]:
                        for start in range(0, len(passages), 64):
                            ids = [p.passage_id for p in passages[start : start + 64]]
                            records = vector.get(ids=ids, include=["embeddings"])
                            values = records["embeddings"]
                            if (
                                values is None
                                or set(records["ids"]) != set(ids)
                                or len(records["ids"]) != len(ids)
                            ):
                                raise RetrievalError(
                                    "Retained embeddings are incomplete. Rebuild before deleting this document."
                                )
                            checked = validate_vectors(
                                np.asarray(values).tolist(), len(ids), manifest.identity.dimensions
                            )
                            mapped = dict(zip(records["ids"], checked, strict=True))
                            yield ids, [mapped[pid] for pid in ids]

                    self.repository.publish(
                        active,
                        manifest.identity,
                        batches(),
                        expected_revision=expected_revision,
                        library_source=source,
                    )
        return LibraryResult(
            changed=True, collection_id=collection_id, warnings=self.repository.cleanup()
        )

    def delete_collection(self, collection_id: str, expected_revision: int) -> LibraryResult:
        self._entry(collection_id, expected_revision)
        self.repository.delete_collection(collection_id, expected_revision)
        return LibraryResult(
            changed=True, collection_id=collection_id, warnings=self.repository.cleanup()
        )

    def status(self, collection_id: str) -> LibraryStatus:
        source, _ = self.repository.library_entry(collection_id)
        generation = self.repository.active_generation(collection_id)
        if generation is None:
            return LibraryStatus(
                status="not_indexed",
                documents=len(source.documents),
                detail="Saved sources have no active search index.",
            )
        try:
            active, manifest = self.repository.load(collection_id)
            self.repository.vectors(active, manifest)
        except RetrievalError:
            return LibraryStatus(
                status="failed",
                documents=len(source.documents),
                generation=generation,
                detail="Index is missing or inconsistent. Rebuild from saved library sources.",
            )
        status = "indexed" if fingerprint(source) == manifest.source_fingerprint else "stale"
        return LibraryStatus(
            status=status,
            documents=len(source.documents),
            indexed_documents=len(active.documents),
            indexed_passages=manifest.passage_count,
            generation=manifest.generation,
            detail="Current saved sources are searchable."
            if status == "indexed"
            else "Saved sources differ from the active index; build to include pending changes.",
        )

    def resolve(
        self,
        collection_id: str,
        passage_id: str,
        *,
        generation: str | None = None,
        quote: str | None = None,
    ) -> Citation:
        try:
            active, manifest = self.repository.load(collection_id)
        except RetrievalError:
            raise RetrievalError(
                "This reference is outdated or the collection has no readable active index."
            ) from None
        if generation is not None and generation != manifest.generation:
            raise RetrievalError(
                "This reference is outdated because the saved index changed. Ask again or browse current sources."
            )
        for document in active.documents:
            for passage in document.passages:
                if passage.passage_id == passage_id:
                    excerpt = passage.text if quote is None else quote
                    if not excerpt.strip() or excerpt not in passage.text:
                        raise RetrievalError(
                            "The cited excerpt no longer matches the active source."
                        )
                    start = passage.text.index(excerpt)
                    if self.repository.active_generation(collection_id) != manifest.generation:
                        raise RetrievalError(
                            "The active source changed during inspection. Reload this reference."
                        )
                    return Citation(
                        passage=passage,
                        title=document.title,
                        filename=document.filename,
                        content_hash=document.content_hash,
                        quote=excerpt,
                        quote_start=start,
                        quote_end=start + len(excerpt),
                    )
        raise RetrievalError(
            "This passage is outdated, deleted or not part of the active collection."
        )
