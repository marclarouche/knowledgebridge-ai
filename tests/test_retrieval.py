"""Real Chroma/FTS snapshots, controlled embeddings, failures and offline UI coverage."""

import socket
import sqlite3
from contextlib import closing

import pytest

from knowledgebridge.config import ChunkSettings, RetrievalSettings, Settings
from knowledgebridge.embedding_adapter import OllamaEmbedder, validate_vectors
from knowledgebridge.index_repository import IndexRepository, query_expression
from knowledgebridge.indexing import reindex_document
from knowledgebridge.ingestion import ingest
from knowledgebridge.models import KnowledgeCollection
from knowledgebridge.retrieval_models import EmbeddingIdentity, RetrievalError
from knowledgebridge.retriever import fuse, retrieve


class FakeEmbedder:
    """Deterministic test vectors with an explicit paraphrase signal; not a model benchmark."""

    digest = "fixture-digest"

    def identity(self):
        return EmbeddingIdentity(model="embeddinggemma:latest", digest=self.digest, dimensions=3)

    def embed(self, texts):
        return [
            [1.0, 0.01, 0.01]
            if any(t in text.lower() for t in ("auth_required", "credentials", "token"))
            else [0.01, 1.0, 0.01]
            if "page_size" in text.lower()
            else [0.01, 0.01, 1.0]
            for text in texts
        ]


@pytest.fixture
def collection():
    collection = KnowledgeCollection(title="Fictional retrieval test")
    for name, data in [
        ("api.md", b"# Auth\nAUTH_REQUIRED means a workspace token is missing."),
        ("limits.txt", b"Maximum page_size is 100."),
        ("config.txt", b"session_idle_minutes defaults to 30."),
    ]:
        collection, result = ingest(collection, data, name, Settings(), version="2.0")
        assert result.accepted
    return collection


@pytest.fixture
def built(tmp_path, collection):
    repository = IndexRepository(tmp_path / "index")
    manifest = repository.build(collection, FakeEmbedder(), RetrievalSettings())
    return repository, manifest


def test_real_persistence_keyword_semantic_and_hybrid(built, collection):
    repository, manifest = built
    reopened = IndexRepository(repository.root)
    restored, other = reopened.load(collection.collection_id)
    assert manifest == other and restored.index_status.value == "indexed"
    keyword = retrieve(
        reopened, collection.collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()
    )
    assert keyword.hits[0].filename == "api.md"
    assert keyword.hits[0].passage == collection.documents[0].passages[0]
    semantic = retrieve(
        reopened,
        collection.collection_id,
        "What if credentials are absent?",
        "semantic",
        RetrievalSettings(),
        FakeEmbedder(),
    )
    assert semantic.hits[0].filename == "api.md"
    hybrid = retrieve(
        reopened,
        collection.collection_id,
        "AUTH_REQUIRED",
        "hybrid",
        RetrievalSettings(),
        FakeEmbedder(),
    )
    assert hybrid.hits[0].methods == ["keyword", "semantic"]
    assert len({h.passage.passage_id for h in hybrid.hits}) == len(hybrid.hits)
    assert hybrid.hits[0].passage.location.document_version == "2.0"
    assert not retrieve(
        reopened, collection.collection_id, "zxqnonexistent", "keyword", RetrievalSettings()
    ).hits


def test_keyword_no_ollama_or_network(built, collection, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    result = retrieve(
        built[0], collection.collection_id, "page_size", "keyword", RetrievalSettings()
    )
    assert result.hits[0].filename == "limits.txt"


def test_model_change_requires_rebuild_but_keyword_stays_usable(built, collection):
    embedder = FakeEmbedder()
    embedder.digest = "changed"
    with pytest.raises(RetrievalError, match="changed"):
        retrieve(
            built[0], collection.collection_id, "token", "hybrid", RetrievalSettings(), embedder
        )
    assert retrieve(
        built[0], collection.collection_id, "token", "keyword", RetrievalSettings()
    ).hits


def test_failed_rebuild_preserves_active_snapshot(built, collection):
    class Broken(FakeEmbedder):
        def embed(self, texts):
            raise RetrievalError("Fixture failure")

    repository, original = built
    with pytest.raises(RetrievalError):
        repository.build(collection, Broken(), RetrievalSettings())
    assert repository.load(collection.collection_id)[1] == original
    assert retrieve(
        repository,
        collection.collection_id,
        "page_size",
        "hybrid",
        RetrievalSettings(),
        FakeEmbedder(),
    ).hits


def test_reindex_rechunks_saved_source_atomically(built, collection):
    repository, before = built
    settings = Settings(chunking=ChunkSettings(max_words=3, max_chars=32, overlap_words=0))
    after = reindex_document(
        repository,
        collection.collection_id,
        collection.documents[0].document_id,
        settings,
        FakeEmbedder(),
    )
    restored, _ = repository.load(collection.collection_id)
    assert after.generation != before.generation
    assert (
        restored.documents[0].passages[0].passage_id
        != collection.documents[0].passages[0].passage_id
    )
    assert all(len(p.text) <= 32 for p in restored.documents[0].passages)
    assert repository.vectors(restored, after).count() == after.passage_count


def test_missing_vectors_and_fts_corruption_fail_actionably(built, collection):
    repository, manifest = built
    source, _ = repository.load(collection.collection_id)
    vector = repository.vectors(source, manifest)
    vector.delete(ids=[source.documents[0].passages[0].passage_id])
    with pytest.raises(RetrievalError, match="inconsistent"):
        retrieve(
            repository,
            collection.collection_id,
            "token",
            "semantic",
            RetrievalSettings(),
            FakeEmbedder(),
        )
    with closing(sqlite3.connect(repository.database)) as db, db:
        db.execute(
            "DELETE FROM passages WHERE passage_id=?", (source.documents[0].passages[0].passage_id,)
        )
    with pytest.raises(RetrievalError, match="inconsistent"):
        repository.load(collection.collection_id)


def test_collection_isolation(built, collection):
    repository, _ = built
    other, _ = ingest(
        KnowledgeCollection(title="Other"), b"Unique unrelated source.", "other.txt", Settings()
    )
    repository.build(other, FakeEmbedder(), RetrievalSettings())
    assert not retrieve(
        repository, other.collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()
    ).hits
    assert retrieve(
        repository, collection.collection_id, "AUTH_REQUIRED", "keyword", RetrievalSettings()
    ).hits


def test_fusion_deduplication_and_deterministic_ties():
    assert fuse(["b", "a", "a"], ["a", "b"], 60) == [("a", 1 / 61 + 1 / 62), ("b", 1 / 61 + 1 / 62)]
    assert (
        query_expression('page_size OR " --flag /v2/reports; DROP TABLE')
        == '"page_size" OR "or" OR "flag" OR "v2" OR "reports" OR "drop" OR "table"'
    )


@pytest.mark.parametrize(
    "raw",
    [
        [],
        [[0, 0]],
        [[True, 1]],
        [[float("nan"), 1]],
        [[float("inf"), 1]],
        [[1], [1, 2]],
        [[1e308, 1e308]],
    ],
)
def test_bad_embedding_responses(raw):
    with pytest.raises(RetrievalError):
        validate_vectors(raw, 1)


@pytest.mark.parametrize(
    "changes",
    [{"host": "example.com"}, {"host": "127.0.0.1.evil"}, {"batch_size": 99}, {"top_k": 100}],
)
def test_settings_bounds(changes):
    with pytest.raises(ValueError):
        RetrievalSettings(**changes)


def test_adapter_request_batches_truncate_and_cloud_rejection(monkeypatch):
    embedder = OllamaEmbedder(RetrievalSettings(batch_size=2))
    calls = []

    def request(path, body=None):
        calls.append((path, body))
        if path == "/api/tags":
            return {"models": [{"name": "embeddinggemma:latest", "digest": "digest"}]}
        if path == "/api/show":
            return {}
        return {"model": "embeddinggemma:latest", "embeddings": [[1.0, 0.0] for _ in body["input"]]}

    monkeypatch.setattr(embedder, "_request", request)
    assert embedder.identity().dimensions == 2
    assert len(embedder.embed(["one", "two", "three"])) == 3
    assert all(body["truncate"] is False for path, body in calls if path == "/api/embed")
    monkeypatch.setattr(
        embedder,
        "_request",
        lambda path, body=None: (
            {"models": [{"name": "embeddinggemma:latest", "digest": "digest"}]}
            if path == "/api/tags"
            else {"remote_host": "https://cloud.invalid"}
        ),
    )
    with pytest.raises(RetrievalError, match="Cloud"):
        embedder.identity()


def test_adapter_unavailable_and_invalid_queries(built, collection, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("Sensitive exception content")

    monkeypatch.setattr("http.client.HTTPConnection.request", unavailable)
    with pytest.raises(RetrievalError, match="unavailable") as error:
        OllamaEmbedder(RetrievalSettings()).identity()
    assert "Sensitive" not in str(error.value)
    for query in (" ", "x" * 2001):
        with pytest.raises(RetrievalError):
            retrieve(built[0], collection.collection_id, query, "keyword", RetrievalSettings())


def test_build_and_chroma_query_make_no_network_calls(tmp_path, collection, monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("No network permitted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    repository = IndexRepository(tmp_path / "offline")
    repository.build(collection, FakeEmbedder(), RetrievalSettings())
    assert retrieve(
        repository,
        collection.collection_id,
        "credentials",
        "hybrid",
        RetrievalSettings(),
        FakeEmbedder(),
    ).hits
    assert not calls


def test_model_changes_mid_build_never_activate(tmp_path, collection):
    class Changing(FakeEmbedder):
        def embed(self, texts):
            result = super().embed(texts)
            self.digest = "changed-after-embedding"
            return result

    repository = IndexRepository(tmp_path / "changing")
    with pytest.raises(RetrievalError, match="changed"):
        repository.build(collection, Changing(), RetrievalSettings())
    assert repository.catalog() == []


def test_sqlite_failure_after_vectors_keeps_previous_snapshot(built, collection, monkeypatch):
    repository, before = built
    connect = repository._connect

    class FailCommit(sqlite3.Connection):
        def executemany(self, *args, **kwargs):
            raise sqlite3.OperationalError("Fixture storage failure")

    monkeypatch.setattr(
        repository, "_connect", lambda: sqlite3.connect(repository.database, factory=FailCommit)
    )
    with pytest.raises(RetrievalError, match="previous active"):
        repository.build(collection, FakeEmbedder(), RetrievalSettings())
    monkeypatch.setattr(repository, "_connect", connect)
    assert repository.load(collection.collection_id)[1] == before


def test_missing_catalog_table_is_not_silently_recreated(built):
    repository, _ = built
    with closing(sqlite3.connect(repository.database)) as db, db:
        db.execute("DROP TABLE snapshots")
    with pytest.raises(RetrievalError, match="missing"):
        IndexRepository(repository.root)


def test_ui_reopens_saved_collection_and_searches_offline(tmp_path, collection, monkeypatch):
    from streamlit.testing.v1 import AppTest

    root = tmp_path / "ui-data"
    repository = IndexRepository(root)
    repository.build(collection, FakeEmbedder(), RetrievalSettings())
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(root))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise OSError("Network forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    app_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=45).run()
    assert not at.exception and len(at.session_state.collections) == 1
    at.radio[0].set_value("Index and Search").run()
    assert not at.exception
    mode = next(w for w in at.selectbox if w.label == "Retrieval mode")
    mode.set_value("keyword")
    next(w for w in at.text_input if w.label == "Search question or technical term").set_value(
        "AUTH_REQUIRED"
    )
    next(w for w in at.button if w.label == "Retrieve source passages").click().run()
    assert not at.exception
    assert any("AUTH_REQUIRED" in w.value for w in at.code)
    assert any(collection.documents[0].passages[0].passage_id in w.value for w in at.text)
    # A semantic failure is explicit; it leaves the saved collection intact.
    next(w for w in at.selectbox if w.label == "Retrieval mode").set_value("hybrid")
    next(w for w in at.button if w.label == "Retrieve source passages").click().run()
    assert not at.exception and at.error
    assert repository.load(collection.collection_id)[0].documents


def test_keyword_ranking_is_independent_of_other_snapshots(built, collection):
    repository, manifest = built
    before = repository.keyword(manifest, "AUTH_REQUIRED page_size", 10)
    other, _ = ingest(
        KnowledgeCollection(title="Other corpus"),
        b"AUTH_REQUIRED " * 1000,
        "unrelated.txt",
        Settings(),
    )
    repository.build(other, FakeEmbedder(), RetrievalSettings())
    assert repository.keyword(manifest, "AUTH_REQUIRED page_size", 10) == before


@pytest.mark.parametrize(
    "status,payload",
    [
        (302, b"{}"),
        (500, b'{"error":"private source"}'),
        (200, b"not json"),
        (200, b"[]"),
        (200, b"x" * (8 * 1024 * 1024 + 1)),
    ],
)
def test_http_adapter_bounds_and_does_not_follow_redirects(monkeypatch, status, payload):
    calls = []

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "127.0.0.1" and timeout <= 300

        def request(self, method, path, **kwargs):
            calls.append((method, path))

        def getresponse(self):
            class Response:
                def read(self, count):
                    return payload[:count]

            response = Response()
            response.status = status
            return response

        def close(self):
            pass

    monkeypatch.setattr("http.client.HTTPConnection", Connection)
    with pytest.raises(RetrievalError) as error:
        OllamaEmbedder(RetrievalSettings())._request("/api/tags")
    assert "private source" not in str(error.value)
    assert calls == [("GET", "/api/tags")]


def test_chroma_backend_stays_embedded_when_environment_requests_http(
    tmp_path, collection, monkeypatch
):
    monkeypatch.setenv("CHROMA_API_IMPL", "chromadb.api.fastapi.FastAPI")
    repository = IndexRepository(tmp_path / "embedded-only")
    settings = repository._client().get_settings()
    assert settings.chroma_api_impl == "chromadb.api.rust.RustBindingsAPI"
    assert not settings.anonymized_telemetry and not settings.allow_reset
    manifest = repository.build(collection, FakeEmbedder(), RetrievalSettings())
    assert repository.vectors(collection, manifest)._embedding_function is None
