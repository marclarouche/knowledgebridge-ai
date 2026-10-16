"""Library migration, durable sources, transactional lifecycle and citation navigation."""

import socket
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from test_retrieval import FakeEmbedder

from knowledgebridge.config import RetrievalSettings, Settings
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.ingestion import ingest
from knowledgebridge.library import LibraryManager
from knowledgebridge.models import KnowledgeCollection
from knowledgebridge.retrieval_models import RetrievalError
from knowledgebridge.retriever import retrieve

pytest_plugins = ["test_retrieval"]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def library(tmp_path, collection):
    repository = IndexRepository(tmp_path / "library")
    repository.build(collection, FakeEmbedder(), RetrievalSettings())
    return repository, LibraryManager(repository), collection.collection_id


def test_empty_collection_and_pending_import_survive_reopen(tmp_path):
    repository = IndexRepository(tmp_path / "saved")
    manager = LibraryManager(repository)
    source = manager.create("Persistent empty")
    reopened = IndexRepository(repository.root)
    source, revision = reopened.library_entry(source.collection_id)
    assert source.title == "Persistent empty" and not source.documents
    updated, _ = ingest(source, b"Unindexed pending source", "pending.txt", Settings())
    reopened.save_library(updated, revision)
    restored, _ = IndexRepository(repository.root).library_entry(source.collection_id)
    assert restored.documents and manager.status(source.collection_id).status == "not_indexed"


def test_v1_migration_preserves_original_snapshot(library):
    repository, _, collection_id = library
    before = repository.load(collection_id)
    with closing(sqlite3.connect(repository.database)) as db, db:
        for table in ("library", "generations", "tombstones"):
            db.execute(f"DROP TABLE {table}")
        db.execute("PRAGMA user_version=1")
    migrated = IndexRepository(repository.root)
    assert migrated.load(collection_id) == before
    assert migrated.library_entry(collection_id)[0] == before[0]
    assert retrieve(migrated, collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()).hits


def test_replacement_changes_active_sources_and_cleans_obsolete_vectors(library):
    repository, manager, collection_id = library
    _before, manifest = repository.load(collection_id)
    source, revision = repository.library_entry(collection_id)
    old = source.documents[0]
    result = manager.replace_document(
        collection_id,
        old.document_id,
        b"# Updated auth\nNEW_AUTH_CODE now identifies a missing token.",
        "updated.md",
        Settings(),
        FakeEmbedder(),
        revision,
        version="3.0",
    )
    assert result.changed and not result.warnings
    active, new_manifest = repository.load(collection_id)
    assert active.documents[0].version == "3.0" and new_manifest.generation != manifest.generation
    assert active.documents[0].document_id != old.document_id
    assert not retrieve(
        repository, collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()
    ).hits
    assert retrieve(repository, collection_id, "NEW_AUTH_CODE", "keyword", RetrievalSettings()).hits
    with pytest.raises(RetrievalError, match="outdated"):
        manager.resolve(collection_id, old.passages[0].passage_id, generation=manifest.generation)
    assert {c.name for c in repository._client().list_collections()} == {new_manifest.generation}
    with closing(repository._connect()) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM passages WHERE generation=?", (manifest.generation,)
            ).fetchone()[0]
            == 0
        )
    assert manager.status(collection_id).status == "indexed"


@pytest.mark.parametrize(
    "kind", ["malformed", "embedding_failure", "duplicate_other_document", "over_limit"]
)
def test_replacement_failure_is_atomic(library, kind):
    repository, manager, collection_id = library
    old_source, old_revision = repository.library_entry(collection_id)
    old_index = repository.load(collection_id)
    payload, filename, settings = b"Changed valid source", "new.txt", Settings()
    embedder = FakeEmbedder()
    if kind == "malformed":
        payload, filename = b"corrupt", "bad.docx"
    elif kind == "embedding_failure":

        def fail(texts):
            raise RetrievalError("Fixture embedding failure")

        embedder.embed = fail
    elif kind == "duplicate_other_document":
        payload = b"Maximum page_size is 100."
    else:
        settings = Settings(max_file_bytes=1)
    with pytest.raises(RetrievalError):
        manager.replace_document(
            collection_id,
            old_source.documents[0].document_id,
            payload,
            filename,
            settings,
            embedder,
            old_revision,
        )
    assert repository.library_entry(collection_id) == (old_source, old_revision)
    assert repository.load(collection_id) == old_index
    assert retrieve(repository, collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()).hits


def test_identical_replacement_is_noop_but_new_version_invalidates_passages(library):
    repository, manager, collection_id = library
    source, revision = repository.library_entry(collection_id)
    old = source.documents[1]
    original = repository.load(collection_id)[1]
    result = manager.replace_document(
        collection_id,
        old.document_id,
        b"Maximum page_size is 100.",
        old.filename,
        Settings(),
        None,
        revision,
        version=old.version,
    )
    assert not result.changed and repository.library_entry(collection_id)[1] == revision
    assert repository.load(collection_id)[1] == original
    manager.replace_document(
        collection_id,
        old.document_id,
        b"Maximum page_size is 100.",
        old.filename,
        Settings(),
        FakeEmbedder(),
        revision,
        version="3.0",
    )
    updated = repository.load(collection_id)[0].documents[1]
    assert updated.document_id == old.document_id and updated.content_hash == old.content_hash
    assert updated.passages[0].passage_id != old.passages[0].passage_id


def test_document_deletion_uses_existing_vectors_without_ollama_or_network(library, monkeypatch):
    repository, manager, collection_id = library
    before, revision = repository.library_entry(collection_id)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("No network/model allowed")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    manager.delete_document(collection_id, before.documents[0].document_id, revision)
    after, manifest = repository.load(collection_id)
    assert (
        len(after.documents) == 2
        and repository.vectors(after, manifest).count() == manifest.passage_count
    )
    assert not retrieve(
        repository, collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()
    ).hits
    assert retrieve(
        repository, collection_id, "page_size", "semantic", RetrievalSettings(), FakeEmbedder()
    ).hits
    assert not calls


def test_deletion_keeps_pending_imports_without_searching_them(library):
    repository, manager, collection_id = library
    source, revision = repository.library_entry(collection_id)
    source, _ = ingest(source, b"UNINDEXED_PENDING material", "pending.txt", Settings())
    revision = repository.save_library(source, revision)
    assert manager.status(collection_id).status == "stale"
    manager.delete_document(collection_id, source.documents[0].document_id, revision)
    saved, _ = repository.library_entry(collection_id)
    assert len(saved.documents) == 3 and manager.status(collection_id).status == "stale"
    assert not retrieve(
        repository, collection_id, "UNINDEXED_PENDING", "keyword", RetrievalSettings()
    ).hits


def test_delete_last_document_preserves_empty_saved_collection(library):
    repository, manager, collection_id = library
    for _ in range(3):
        source, revision = repository.library_entry(collection_id)
        manager.delete_document(collection_id, source.documents[0].document_id, revision)
    source, _ = repository.library_entry(collection_id)
    assert not source.documents and repository.active_generation(collection_id) is None
    assert manager.status(collection_id).status == "not_indexed"
    assert repository._client().count_collections() == 0
    with pytest.raises(RetrievalError):
        repository.load(collection_id)


def test_collection_deletion_is_scoped_and_cannot_be_resurrected(library):
    repository, manager, collection_id = library
    stale_source, revision = repository.library_entry(collection_id)
    other, _ = ingest(
        KnowledgeCollection(title="Keep this collection"), b"Other source", "other.txt", Settings()
    )
    other_manifest = repository.build(other, FakeEmbedder(), RetrievalSettings())
    manager.delete_collection(collection_id, revision)
    assert [c.collection_id for c, _ in repository.library_records()] == [other.collection_id]
    assert {c.name for c in repository._client().list_collections()} == {other_manifest.generation}
    with pytest.raises(RetrievalError, match="deleted"):
        repository.build(stale_source, FakeEmbedder(), RetrievalSettings())
    with pytest.raises(RetrievalError, match="deleted"):
        repository.save_library(stale_source)


def test_stale_session_and_mid_build_mutations_are_rejected(library):
    repository, manager, collection_id = library
    source, revision = repository.library_entry(collection_id)
    repository.rename(collection_id, "Renamed", revision)
    with pytest.raises(RetrievalError, match="changed"):
        manager.delete_document(collection_id, source.documents[0].document_id, revision)
    with pytest.raises(RetrievalError, match="changed"):
        repository.build(source, FakeEmbedder(), RetrievalSettings())
    current, revision = repository.library_entry(collection_id)

    class Concurrent(FakeEmbedder):
        changed = False

        def embed(self, texts):
            if not self.changed:
                self.changed = True
                repository.rename(collection_id, "Concurrent rename", revision)
            return super().embed(texts)

    with pytest.raises(RetrievalError, match="changed"):
        repository.build(current, Concurrent(), RetrievalSettings(), expected_revision=revision)
    assert repository.library_entry(collection_id)[0].title == "Concurrent rename"


def test_delete_during_index_build_does_not_restore_collection(library):
    repository, manager, collection_id = library
    source, revision = repository.library_entry(collection_id)

    class Concurrent(FakeEmbedder):
        changed = False

        def embed(self, texts):
            if not self.changed:
                self.changed = True
                manager.delete_collection(collection_id, revision)
            return super().embed(texts)

    with pytest.raises(RetrievalError):
        repository.build(source, Concurrent(), RetrievalSettings(), expected_revision=revision)
    assert not repository.library_records() and not repository.catalog()


def test_cleanup_failure_is_reported_without_undoing_deletion(library, monkeypatch):
    repository, manager, collection_id = library
    source, revision = repository.library_entry(collection_id)
    client = repository._client()
    delete = client.delete_collection

    def fail(*args, **kwargs):
        raise OSError("Private failure text")

    monkeypatch.setattr(client, "delete_collection", fail)
    monkeypatch.setattr(repository, "_client", lambda: client)
    result = manager.delete_document(collection_id, source.documents[0].document_id, revision)
    assert result.changed and result.warnings and "Private" not in str(result.warnings)
    assert len(repository.load(collection_id)[0].documents) == 2
    monkeypatch.setattr(client, "delete_collection", delete)
    assert repository.cleanup() == []
    assert client.count_collections() == 1


def test_source_resolution_status_and_corrupt_index_rebuild(library):
    repository, manager, collection_id = library
    source, manifest = repository.load(collection_id)
    passage = source.documents[0].passages[0]
    reference = manager.resolve(
        collection_id, passage.passage_id, generation=manifest.generation, quote="AUTH_REQUIRED"
    )
    assert reference.quote == "AUTH_REQUIRED" and reference.passage == passage
    with pytest.raises(RetrievalError, match="no longer matches"):
        manager.resolve(collection_id, passage.passage_id, quote="invented")
    repository.vectors(source, manifest).delete(ids=[passage.passage_id])
    assert manager.status(collection_id).status == "failed"
    _, revision = repository.library_entry(collection_id)
    manager.index(collection_id, Settings(), FakeEmbedder(), revision)
    assert manager.status(collection_id).status == "indexed"


def test_keyword_corruption_does_not_destroy_library_or_block_rebuild(library):
    repository, manager, collection_id = library
    _, manifest = repository.load(collection_id)
    with closing(repository._connect()) as db, db:
        db.execute(f"DROP TABLE {manifest.generation}")
    assert manager.status(collection_id).status == "failed"
    source, revision = repository.library_entry(collection_id)
    assert source.documents
    manager.index(collection_id, Settings(), FakeEmbedder(), revision)
    assert manager.status(collection_id).status == "indexed"


def test_cleanup_preserves_registered_staging_generations(library):
    repository, _, collection_id = library
    staging = "kb_" + "a" * 32
    with closing(repository._connect()) as db, db:
        db.execute("INSERT INTO generations VALUES (?,?,'staging','')", (staging, collection_id))
    repository._client().create_collection(staging, embedding_function=None)
    assert repository.cleanup() == []
    assert staging in {c.name for c in repository._client().list_collections()}


def test_persistent_collection_ui_rename_and_source_lookup(library, monkeypatch):
    repository, _, collection_id = library
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(repository.root))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    next(w for w in at.text_input if w.label == "New collection title").set_value("Renamed in UI")
    next(w for w in at.button if w.label == "Rename collection").click().run()
    assert not at.exception and repository.library_entry(collection_id)[0].title == "Renamed in UI"
    at.radio[0].set_value("Document Library").run()
    assert not at.exception
    assert next(w for w in at.button if w.label == "Delete document").disabled
    at.radio[0].set_value("Source Explorer").run()
    next(w for w in at.button if w.label == "Inspect selected passage").click().run()
    assert not at.exception and at.code
    next(w for w in at.text_input if w.label == "Passage ID to inspect").set_value(
        "outdated-passage"
    )
    next(w for w in at.button if w.label == "Inspect passage ID").click().run()
    assert not at.exception and at.warning


def test_answer_reference_navigation_and_stale_answer_warning(library, monkeypatch):
    from test_answering import FixtureGenerator, claim_draft

    repository, manager, collection_id = library
    source, _ = repository.library_entry(collection_id)
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(repository.root))
    monkeypatch.setattr(
        "knowledgebridge.embedding_adapter.OllamaEmbedder", lambda settings: FakeEmbedder()
    )
    monkeypatch.setattr(
        "knowledgebridge.answer_generator.OllamaGenerator",
        lambda *args: FixtureGenerator(claim_draft(source)),
    )
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    at.radio[0].set_value("Ask KnowledgeBridge").run()
    next(w for w in at.text_input if w.label == "Question about this collection").set_value(
        "AUTH_REQUIRED"
    )
    next(w for w in at.button if w.label == "Ask using saved sources").click().run()
    assert not at.exception and any(w.value == "Status: answered" for w in at.text)
    next(w for w in at.button if w.label == "Inspect source").click().run()
    assert not at.exception and at.radio[0].value == "Source Explorer" and at.code
    current, revision = repository.library_entry(collection_id)
    manager.replace_document(
        collection_id,
        current.documents[0].document_id,
        b"New replacement source",
        "new.txt",
        Settings(),
        FakeEmbedder(),
        revision,
        version="3.0",
    )
    at.run()
    assert not at.exception and any("outdated" in w.value for w in at.warning)
    at.radio[0].set_value("Ask KnowledgeBridge").run()
    assert not at.exception and any("older index" in w.value for w in at.warning)
    assert not any(w.value.startswith("Status: answered") for w in at.text)


def test_collection_ui_delete_clears_selection_safely(tmp_path, monkeypatch):
    repository = IndexRepository(tmp_path / "empty-ui")
    LibraryManager(repository).create("Disposable empty UI fixture")
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(repository.root))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    next(
        w for w in at.checkbox if w.label == "I understand this removes the selected collection"
    ).check().run()
    next(w for w in at.button if w.label == "Delete collection").click().run()
    assert (
        not at.exception and not repository.library_records() and not at.session_state.collections
    )


def test_corrupt_index_status_is_visible_and_library_ui_still_opens(library, monkeypatch):
    repository, _, collection_id = library
    _, manifest = repository.load(collection_id)
    with closing(repository._connect()) as db, db:
        db.execute(f"DROP TABLE {manifest.generation}")
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(repository.root))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    assert not at.exception and at.session_state.collections
    at.radio[0].set_value("Index and Search").run()
    assert not at.exception and at.error
    assert not next(w for w in at.button if w.label == "Build / rebuild collection index").disabled


def test_stale_document_session_cannot_restore_deleted_content(library):
    repository, manager, collection_id = library
    stale, revision = repository.library_entry(collection_id)
    manager.delete_document(collection_id, stale.documents[0].document_id, revision)
    with pytest.raises(RetrievalError, match="changed"):
        repository.build(stale, FakeEmbedder(), RetrievalSettings())
    with pytest.raises(RetrievalError, match="changed"):
        repository.save_library(stale, revision)


def test_stale_ui_form_cannot_overwrite_an_external_rename(library, monkeypatch):
    repository, _, collection_id = library
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(repository.root))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    next(w for w in at.text_input if w.label == "New collection title").set_value(
        "Stale browser rename"
    )
    _, revision = repository.library_entry(collection_id)
    repository.rename(collection_id, "Saved in another session", revision)
    next(w for w in at.button if w.label == "Rename collection").click().run()
    assert not at.exception and at.error
    assert repository.library_entry(collection_id)[0].title == "Saved in another session"
