"""SQLite catalog/FTS5 and immutable Chroma generations with atomic activation."""

import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from functools import wraps
from pathlib import Path
from typing import Literal
from uuid import uuid4

import chromadb
import numpy as np
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from knowledgebridge.config import RetrievalSettings
from knowledgebridge.embedding_adapter import Embedder, validate_vectors
from knowledgebridge.models import IndexStatus, KnowledgeCollection, now
from knowledgebridge.retrieval_models import EmbeddingIdentity, IndexManifest, RetrievalError


def fingerprint(collection: KnowledgeCollection) -> str:
    """Fingerprint source content, versions, locations and chunk settings, not UI status."""
    records = [
        d.model_dump(mode="json", exclude={"index_status", "imported_at"})
        for d in collection.documents
    ]
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def query_expression(query: str) -> str:
    """Quote Unicode terms; users cannot inject SQL or FTS operators.

    The unicode61 tokenizer retains underscores; punctuation in API paths/flags is
    split consistently. OR gives partial keyword coverage; BM25 orders candidates.
    """
    terms = list(dict.fromkeys(re.findall(r"\w+", query.lower(), re.UNICODE)))[:64]
    return " OR ".join('"' + term + '"' for term in terms)


def fts_table(generation: str) -> str:
    """Only internally generated identifiers can become SQL identifiers."""
    if not re.fullmatch(r"kb_[0-9a-f]{32}", generation):
        raise RetrievalError("Index generation identifier is invalid. Rebuild the collection.")
    return generation


def storage_boundary[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Translate OS/SQLite errors without leaking source content or SQL values."""

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except RetrievalError:
            raise
        except (sqlite3.Error, OSError, ValueError):
            raise RetrievalError(
                "Local library operation failed. Refresh status and check storage before retrying."
            ) from None

    return wrapped


class IndexRepository:
    """Application-owned path supplied by application/configuration, never documents."""

    def __init__(self, root: Path):
        self.root = root
        try:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            raise RetrievalError(
                "Local index directory is unavailable. Check the configured path and permissions."
            ) from None
        self.database = root / "catalog.sqlite3"
        try:
            with closing(self._connect()) as db, db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                tables = {
                    row[0]
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if version in (1, 2) and not {"snapshots", "passages"}.issubset(tables):
                    raise RetrievalError(
                        "Index catalog tables are missing. Restore a backup or rebuild from originals."
                    )
                if version == 2 and not {"library", "generations", "tombstones"}.issubset(tables):
                    raise RetrievalError(
                        "Library catalog tables are missing. Restore a local backup."
                    )
                if version not in (0, 1, 2):
                    raise RetrievalError(
                        "Unsupported index schema. Restore a compatible local backup."
                    )
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        collection_id TEXT PRIMARY KEY, generation TEXT NOT NULL,
                        manifest TEXT NOT NULL, source TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS passages (
                        generation TEXT NOT NULL, passage_id TEXT NOT NULL, text TEXT NOT NULL,
                        PRIMARY KEY(generation, passage_id)
                    );
                    CREATE TABLE IF NOT EXISTS library (
                        collection_id TEXT PRIMARY KEY, source TEXT NOT NULL, revision INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS generations (
                        generation TEXT PRIMARY KEY, collection_id TEXT NOT NULL,
                        state TEXT NOT NULL, created_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS tombstones (
                        collection_id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
                    INSERT OR IGNORE INTO library SELECT collection_id, source, 1 FROM snapshots;
                    INSERT OR IGNORE INTO generations
                        SELECT generation, collection_id, 'active', '' FROM snapshots;
                    PRAGMA user_version=2;
                """)
        except sqlite3.Error:
            raise RetrievalError(
                "Cannot open the local index catalog. Restore or rebuild from originals."
            ) from None

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10)
        db.execute("PRAGMA trusted_schema=OFF")
        return db

    def _client(self) -> chromadb.api.ClientAPI:
        return chromadb.PersistentClient(
            path=str(self.root / "chroma"),
            settings=ChromaSettings(
                chroma_api_impl="chromadb.api.rust.RustBindingsAPI",
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )

    def catalog(self) -> list[tuple[KnowledgeCollection, IndexManifest]]:
        try:
            with closing(self._connect()) as db:
                ids = [
                    row[0]
                    for row in db.execute(
                        "SELECT collection_id FROM snapshots ORDER BY collection_id"
                    )
                ]
            return [self.load(identifier) for identifier in ids]
        except sqlite3.Error:
            raise RetrievalError(
                "Cannot read index catalog. Restore or rebuild from originals."
            ) from None

    def load(self, collection_id: str) -> tuple[KnowledgeCollection, IndexManifest]:
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT source, manifest, generation FROM snapshots WHERE collection_id=?",
                    (collection_id,),
                ).fetchone()
                if row is None:
                    raise RetrievalError("Collection has no saved index. Build it first.")
                collection = KnowledgeCollection.model_validate_json(row[0])
                manifest = IndexManifest.model_validate_json(row[1])
                passages = {p.passage_id: p.text for d in collection.documents for p in d.passages}
                indexed = dict(
                    db.execute(
                        "SELECT passage_id, text FROM passages WHERE generation=?", (row[2],)
                    )
                )
                table = fts_table(manifest.generation)
                fts_rows = list(db.execute(f"SELECT passage_id, text FROM {table}"))  # nosec B608
                if dict(fts_rows) != passages or len(fts_rows) != len(passages):
                    raise ValueError("Keyword generation mismatch")
                count = db.execute(
                    "SELECT count(*) FROM passages WHERE generation=?", (row[2],)
                ).fetchone()[0]
                if (
                    collection.collection_id != collection_id
                    or manifest.collection_id != collection_id
                    or manifest.generation != row[2]
                    or manifest.source_fingerprint != fingerprint(collection)
                    or manifest.passage_count != len(passages)
                    or indexed != passages
                    or count != len(passages)
                ):
                    raise ValueError("Invalid snapshot")
                return collection, manifest
        except RetrievalError:
            raise
        except (sqlite3.Error, ValueError, TypeError):
            raise RetrievalError(
                "Index catalog is inconsistent. Rebuild from retained sources or originals."
            ) from None

    def vectors(self, collection: KnowledgeCollection, manifest: IndexManifest) -> Collection:
        """Fail on a missing generation or mismatched IDs rather than return partial results."""
        try:
            if not (self.root / "chroma" / "chroma.sqlite3").is_file():
                raise ValueError("Missing vector database")
            vector = self._client().get_collection(manifest.generation, embedding_function=None)
            expected = {p.passage_id for d in collection.documents for p in d.passages}
            actual = vector.get(include=[])["ids"]
            if vector.count() != len(expected) or set(actual) != expected:
                raise ValueError("Mismatched passages")
            metadata = vector.metadata or {}
            if metadata.get("identity") != manifest.identity.model_dump_json():
                raise ValueError("Mismatched embedding identity")
            return vector
        except Exception:  # noqa: BLE001 — isolate third-party storage failures from UI/source data
            raise RetrievalError(
                "Vector index is missing or inconsistent. Rebuild this collection."
            ) from None

    @storage_boundary
    def build(
        self,
        collection: KnowledgeCollection,
        embedder: Embedder,
        settings: RetrievalSettings,
        *,
        expected_revision: int | None = None,
        library_source: KnowledgeCollection | None = None,
    ) -> IndexManifest:
        """Embed a candidate and atomically activate it only if the library is unchanged."""
        if not collection.documents:
            raise RetrievalError("Import documents before building an index.")
        identity = embedder.identity()
        if identity.model != settings.model:
            raise RetrievalError("Embedding adapter does not match configured model.")
        passages = [p for d in collection.documents for p in d.passages]

        def batches() -> Iterable[tuple[list[str], list[list[float]]]]:
            for start in range(0, len(passages), settings.batch_size):
                batch = passages[start : start + settings.batch_size]
                yield (
                    [p.passage_id for p in batch],
                    validate_vectors(
                        embedder.embed([p.text for p in batch]), len(batch), identity.dimensions
                    ),
                )
            if embedder.identity() != identity:
                raise RetrievalError(
                    "Embedding model changed during indexing. Rebuild with a stable model."
                )

        return self.publish(
            collection,
            identity,
            batches(),
            expected_revision=expected_revision,
            library_source=library_source,
        )

    @storage_boundary
    def publish(
        self,
        collection: KnowledgeCollection,
        identity: EmbeddingIdentity,
        batches: Iterable[tuple[list[str], list[list[float]]]],
        *,
        expected_revision: int | None = None,
        library_source: KnowledgeCollection | None = None,
    ) -> IndexManifest:
        """Stage bounded explicit vectors, then compare revisions before atomic activation."""
        if not collection.documents:
            raise RetrievalError("Import documents before building an index.")
        if (
            len(collection.documents) > 1000
            or sum(len(d.passages) for d in collection.documents) > 50000
            or sum(len(s.text) for d in collection.documents for s in d.sections) > 20000000
        ):
            raise RetrievalError("Collection exceeds indexing limits.")
        collection = KnowledgeCollection.model_validate_json(collection.model_dump_json())
        source = KnowledgeCollection.model_validate_json(
            (library_source or collection).model_dump_json()
        )
        if source.collection_id != collection.collection_id:
            raise RetrievalError("Library collection identity mismatch.")
        with closing(self._connect()) as db, db:
            self._not_deleted(db, collection.collection_id)
            prior = db.execute(
                "SELECT source, revision FROM library WHERE collection_id=?",
                (collection.collection_id,),
            ).fetchone()
            revision = prior[1] if prior else None
            if expected_revision is not None and revision != expected_revision:
                raise RetrievalError("Collection changed. Reload before updating it.")
            if prior and expected_revision is None:
                current = KnowledgeCollection.model_validate_json(prior[0])
                if (
                    fingerprint(current) != fingerprint(collection)
                    or current.title != collection.title
                ):
                    raise RetrievalError(
                        "Library sources changed. Reload before building the index."
                    )
            active = db.execute(
                "SELECT generation FROM snapshots WHERE collection_id=?",
                (collection.collection_id,),
            ).fetchone()
            old_generation = active[0] if active else None
            generation = "kb_" + uuid4().hex
            db.execute(
                "INSERT INTO generations VALUES (?,?,'staging',?)",
                (generation, collection.collection_id, now().isoformat()),
            )
        passages = [p for d in collection.documents for p in d.passages]
        manifest = IndexManifest(
            collection_id=collection.collection_id,
            generation=generation,
            identity=identity,
            passage_count=len(passages),
            source_fingerprint=fingerprint(collection),
            indexed_at=now().isoformat(),
        )
        try:
            vector = self._client().create_collection(
                generation,
                embedding_function=None,
                metadata={"hnsw:space": "cosine", "identity": identity.model_dump_json()},
            )
            for ids, values in batches:
                checked = validate_vectors(values, len(ids), identity.dimensions)
                vector.add(ids=ids, embeddings=np.asarray(checked, dtype=np.float32))
            self.vectors(collection, manifest)
            for document in collection.documents:
                document.index_status = IndexStatus.INDEXED
            collection.index_status = IndexStatus.INDEXED
            source = self._status(source, collection)
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                self._not_deleted(db, collection.collection_id)
                self._revision(db, collection.collection_id, revision)
                current = db.execute(
                    "SELECT generation FROM snapshots WHERE collection_id=?",
                    (collection.collection_id,),
                ).fetchone()
                if (current[0] if current else None) != old_generation:
                    raise RetrievalError("The active index changed. Reload and retry.")
                stage = db.execute(
                    "SELECT state FROM generations WHERE generation=?", (generation,)
                ).fetchone()
                if not stage or stage[0] != "staging":
                    raise RetrievalError("Index build was superseded by another library operation.")
                table = fts_table(generation)
                db.execute(f"""CREATE VIRTUAL TABLE {table} USING fts5(
                    passage_id UNINDEXED, text, tokenize = "unicode61 tokenchars '_'"
                )""")
                db.executemany(
                    f"INSERT INTO {table}(passage_id, text) VALUES (?,?)",  # nosec B608
                    [(p.passage_id, p.text) for p in passages],
                )
                db.executemany(
                    "INSERT INTO passages(generation, passage_id, text) VALUES (?,?,?)",
                    [(generation, p.passage_id, p.text) for p in passages],
                )
                db.execute(
                    "INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?)",
                    (
                        collection.collection_id,
                        generation,
                        manifest.model_dump_json(),
                        collection.model_dump_json(),
                    ),
                )
                db.execute(
                    "INSERT OR REPLACE INTO library VALUES (?,?,?)",
                    (source.collection_id, source.model_dump_json(), (revision or 0) + 1),
                )
                db.execute(
                    "UPDATE generations SET state='retired' WHERE collection_id=? AND state='active'",
                    (collection.collection_id,),
                )
                db.execute(
                    "UPDATE generations SET state='active' WHERE generation=?", (generation,)
                )
            return manifest
        except Exception as error:
            try:
                with closing(self._connect()) as db, db:
                    db.execute(
                        "UPDATE generations SET state='retired' WHERE generation=? AND state='staging'",
                        (generation,),
                    )
            except sqlite3.Error:
                pass
            if isinstance(error, RetrievalError):
                raise
            raise RetrievalError(
                "Index build failed; this build did not replace the previous active snapshot. Refresh library status and check local storage."
            ) from None

    @staticmethod
    def _not_deleted(db: sqlite3.Connection, collection_id: str) -> None:
        if db.execute(
            "SELECT 1 FROM tombstones WHERE collection_id=?", (collection_id,)
        ).fetchone():
            raise RetrievalError("This collection was deleted. Create a new collection instead.")

    @staticmethod
    def _revision(db: sqlite3.Connection, collection_id: str, expected: int | None) -> None:
        row = db.execute(
            "SELECT revision FROM library WHERE collection_id=?", (collection_id,)
        ).fetchone()
        if (row[0] if row else None) != expected:
            raise RetrievalError("Collection changed. Reload before updating it.")

    @staticmethod
    def _status(
        source: KnowledgeCollection, active: KnowledgeCollection | None
    ) -> KnowledgeCollection:
        source = KnowledgeCollection.model_validate_json(source.model_dump_json())
        if active is None:
            source.index_status = IndexStatus.NOT_INDEXED
            for document in source.documents:
                document.index_status = IndexStatus.NOT_INDEXED
        else:
            source.index_status = (
                IndexStatus.INDEXED
                if fingerprint(source) == fingerprint(active)
                else IndexStatus.STALE
            )
            indexed = {d.document_id: d for d in active.documents}
            for document in source.documents:
                old = indexed.get(document.document_id)
                if old is None:
                    document.index_status = IndexStatus.NOT_INDEXED
                elif document.model_dump(exclude={"index_status", "imported_at"}) == old.model_dump(
                    exclude={"index_status", "imported_at"}
                ):
                    document.index_status = IndexStatus.INDEXED
                else:
                    document.index_status = IndexStatus.STALE
        return source

    @storage_boundary
    def active_generation(self, collection_id: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT generation FROM snapshots WHERE collection_id=?", (collection_id,)
            ).fetchone()
            return str(row[0]) if row else None

    def library_entry(self, collection_id: str) -> tuple[KnowledgeCollection, int]:
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT source, revision FROM library WHERE collection_id=?", (collection_id,)
                ).fetchone()
                if row is None:
                    raise RetrievalError("Collection is no longer in the saved library. Reload.")
                source = KnowledgeCollection.model_validate_json(row[0])
                if source.collection_id != collection_id:
                    raise ValueError("Identity mismatch")
                return source, int(row[1])
        except (sqlite3.Error, ValueError, TypeError):
            raise RetrievalError(
                "Saved library is unavailable or inconsistent. Restore a local backup."
            ) from None

    def library_records(self) -> list[tuple[KnowledgeCollection, int]]:
        try:
            with closing(self._connect()) as db:
                ids = [
                    row[0]
                    for row in db.execute(
                        "SELECT collection_id FROM library ORDER BY collection_id"
                    )
                ]
            return [self.library_entry(identifier) for identifier in ids]
        except sqlite3.Error:
            raise RetrievalError("Cannot read the saved library. Restore a local backup.") from None

    @storage_boundary
    def save_library(
        self, collection: KnowledgeCollection, expected_revision: int | None = None
    ) -> int:
        collection = KnowledgeCollection.model_validate_json(collection.model_dump_json())
        failed = False
        active = None
        if self.active_generation(collection.collection_id) is not None:
            try:
                active, _ = self.load(collection.collection_id)
            except RetrievalError:
                failed = True
        collection = self._status(collection, active)
        if failed:
            collection.index_status = IndexStatus.FAILED
        try:
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                self._not_deleted(db, collection.collection_id)
                self._revision(db, collection.collection_id, expected_revision)
                revision = (expected_revision or 0) + 1
                db.execute(
                    "INSERT OR REPLACE INTO library VALUES (?,?,?)",
                    (collection.collection_id, collection.model_dump_json(), revision),
                )
            return revision
        except sqlite3.Error:
            raise RetrievalError("Library update failed; saved sources are unchanged.") from None

    @storage_boundary
    def rename(self, collection_id: str, title: str, expected_revision: int) -> None:
        source, revision = self.library_entry(collection_id)
        if revision != expected_revision:
            raise RetrievalError("Collection changed. Reload before renaming.")
        source.title = title.strip()
        source.modified_at = now()
        try:
            source = KnowledgeCollection.model_validate_json(source.model_dump_json())
        except ValueError:
            raise RetrievalError(
                "Enter a nonblank collection title of at most 500 characters."
            ) from None
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._revision(db, collection_id, revision)
            row = db.execute(
                "SELECT source FROM snapshots WHERE collection_id=?", (collection_id,)
            ).fetchone()
            if row:
                active = KnowledgeCollection.model_validate_json(row[0])
                active.title = source.title
                active.modified_at = source.modified_at
                db.execute(
                    "UPDATE snapshots SET source=? WHERE collection_id=?",
                    (active.model_dump_json(), collection_id),
                )
            db.execute(
                "UPDATE library SET source=?, revision=revision+1 WHERE collection_id=?",
                (source.model_dump_json(), collection_id),
            )

    @storage_boundary
    def deactivate(
        self, collection_id: str, source: KnowledgeCollection, expected_revision: int
    ) -> None:
        if source.collection_id != collection_id:
            raise RetrievalError("Library collection identity mismatch.")
        source = self._status(source, None)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._revision(db, collection_id, expected_revision)
            db.execute("DELETE FROM snapshots WHERE collection_id=?", (collection_id,))
            db.execute(
                "UPDATE generations SET state='retired' WHERE collection_id=? AND state='active'",
                (collection_id,),
            )
            db.execute(
                "UPDATE library SET source=?, revision=revision+1 WHERE collection_id=?",
                (source.model_dump_json(), collection_id),
            )

    @storage_boundary
    def delete_collection(self, collection_id: str, expected_revision: int) -> None:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._revision(db, collection_id, expected_revision)
            db.execute(
                "INSERT OR REPLACE INTO tombstones VALUES (?,?)", (collection_id, now().isoformat())
            )
            db.execute("DELETE FROM snapshots WHERE collection_id=?", (collection_id,))
            db.execute("DELETE FROM library WHERE collection_id=?", (collection_id,))
            db.execute(
                "UPDATE generations SET state='retired' WHERE collection_id=?", (collection_id,)
            )

    def cleanup(self) -> list[str]:
        """Remove retired and legacy orphan generations; never touch active/staging data.

        Deletion is logical, not secure disk erasure. Failed cleanup remains retryable.
        """
        warnings: list[str] = []
        try:
            client = self._client() if (self.root / "chroma/chroma.sqlite3").exists() else None
            vector_names = {c.name for c in client.list_collections()} if client else set()
            with closing(self._connect()) as db:
                sql_names = {
                    row[0]
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    if re.fullmatch(r"kb_[0-9a-f]{32}", row[0])
                }
                retired = {
                    row[0]
                    for row in db.execute(
                        "SELECT generation FROM generations WHERE state='retired'"
                    )
                }
            candidates = vector_names | sql_names | retired
            for name in candidates:
                if not re.fullmatch(r"kb_[0-9a-f]{32}", name):
                    continue
                try:
                    with closing(self._connect()) as db, db:
                        db.execute("BEGIN IMMEDIATE")
                        if db.execute(
                            "SELECT 1 FROM snapshots WHERE generation=?", (name,)
                        ).fetchone():
                            continue
                        state = db.execute(
                            "SELECT state FROM generations WHERE generation=?", (name,)
                        ).fetchone()
                        if state and state[0] == "staging":
                            continue
                        if client and name in vector_names:
                            client.delete_collection(name)
                        db.execute(f"DROP TABLE IF EXISTS {fts_table(name)}")
                        db.execute("DELETE FROM passages WHERE generation=?", (name,))
                        db.execute("DELETE FROM generations WHERE generation=?", (name,))
                except Exception:  # noqa: BLE001 — cleanup must not undo a committed library change
                    warnings.append(
                        "Obsolete index data could not be fully removed. Retry local cleanup."
                    )
        except Exception:  # noqa: BLE001 — native database failures become a safe retryable warning
            warnings.append(
                "Local index cleanup is unavailable. Active library changes remain saved."
            )
        return list(dict.fromkeys(warnings))

    def keyword(self, manifest: IndexManifest, query: str, limit: int) -> list[tuple[str, float]]:
        expression = query_expression(query)
        if not expression:
            return []
        try:
            with closing(self._connect()) as db:
                return [
                    (str(row[0]), float(row[1]))
                    for row in db.execute(
                        f"SELECT passage_id, bm25({fts_table(manifest.generation)}) AS score "  # nosec B608
                        f"FROM {fts_table(manifest.generation)} WHERE {fts_table(manifest.generation)} MATCH ? "
                        "ORDER BY score, passage_id LIMIT ?",
                        (expression, limit),
                    )
                ]
        except sqlite3.Error:
            raise RetrievalError("Keyword index cannot be read. Rebuild the collection.") from None

    def semantic(
        self,
        collection: KnowledgeCollection,
        manifest: IndexManifest,
        embedding: list[float],
        limit: int,
    ) -> list[tuple[str, float]]:
        try:
            vector = self.vectors(collection, manifest)
            checked = validate_vectors([embedding], 1, manifest.identity.dimensions)
            result = vector.query(
                query_embeddings=np.asarray(checked, dtype=np.float32),
                n_results=min(limit, manifest.passage_count),
                include=["distances"],
            )
            distances = result["distances"]
            if distances is None or len(result["ids"]) != 1 or len(distances) != 1:
                raise ValueError("Invalid vector result")
            ids = result["ids"][0]
            values = distances[0]
            if len(ids) != len(values) or any(not math.isfinite(v) for v in values):
                raise ValueError("Invalid vector distances")
            return sorted(zip(ids, values, strict=True), key=lambda item: (item[1], item[0]))
        except RetrievalError:
            raise
        except Exception:  # noqa: BLE001 — isolate third-party storage failures from UI/source data
            raise RetrievalError("Semantic index cannot be read. Rebuild the collection.") from None


SearchMode = Literal["keyword", "semantic", "hybrid"]
