"""Evidence gates, exact active citations, structured failures and offline UI."""

import json
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from test_retrieval import FakeEmbedder

from knowledgebridge.answer_generator import OllamaGenerator
from knowledgebridge.answer_models import DraftAnswer, GenerationIdentity
from knowledgebridge.answering import ask, bounded_context
from knowledgebridge.citations import CitationValidationError, validate_citations
from knowledgebridge.config import GenerationSettings, RetrievalSettings, Settings
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.retrieval_models import RetrievalError
from knowledgebridge.retriever import retrieve

pytest_plugins = ["test_retrieval"]


class FixtureGenerator:
    def __init__(self, draft, review=None):
        self.draft = draft
        self.review = review or {
            "supported_claims": [0],
            "confirmed_conflicts": [],
            "question_fully_addressed": True,
            "relevant_evidence": True,
            "unresolved_conflict": False,
        }
        self.calls = []

    def identity(self):
        return GenerationIdentity(model="qwen3-vl:4b-instruct", digest="fixture")

    def complete(self, instruction, payload, schema):
        self.calls.append((instruction, payload, schema))
        response = self.draft if len(self.calls) == 1 else self.review
        return response if isinstance(response, str) else json.dumps(response)


@pytest.fixture
def indexed(tmp_path, collection):
    repository = IndexRepository(tmp_path / "index")
    repository.build(collection, FakeEmbedder(), RetrievalSettings())
    return repository, collection


def claim_draft(collection, text="A missing workspace token causes AUTH_REQUIRED."):
    return {
        "status": "answered",
        "claims": [
            {
                "text": text,
                "evidence": [
                    {
                        "passage_id": collection.documents[0].passages[0].passage_id,
                        "quote": "AUTH_REQUIRED means a workspace token is missing.",
                    }
                ],
            }
        ],
        "conflicts": [],
    }


def test_supported_answer_has_resolved_exact_quotes(indexed):
    repository, collection = indexed
    generator = FixtureGenerator(claim_draft(collection))
    result = ask(
        repository,
        collection.collection_id,
        "What causes AUTH_REQUIRED?",
        Settings(),
        FakeEmbedder(),
        generator,
    )
    assert result.status == "answered" and result.review_required
    assert len(generator.calls) == 2 and result.citations
    citation = result.citations[0]
    assert citation.passage.text[citation.quote_start : citation.quote_end] == citation.quote
    assert citation.title == collection.documents[0].title
    assert citation.passage.location.document_version == "2.0"
    assert generator.calls[0][1]["question"] == "What causes AUTH_REQUIRED?"


@pytest.mark.parametrize(
    "change", ["fake_id", "invented_quote", "outside_context", "stale_snapshot"]
)
def test_invalid_or_stale_citations_never_display_draft(indexed, change):
    repository, collection = indexed
    draft = claim_draft(collection)
    generator = FixtureGenerator(draft)
    if change == "fake_id":
        draft["claims"][0]["evidence"][0]["passage_id"] = "fake"
    elif change == "invented_quote":
        draft["claims"][0]["evidence"][0]["quote"] = "A fabricated command."
    elif change == "outside_context":
        # The active passage is valid, but it was not supplied in the actual draft context.
        context = retrieve(
            repository,
            collection.collection_id,
            "token",
            "hybrid",
            RetrievalSettings(),
            FakeEmbedder(),
        ).hits
        parsed = DraftAnswer.model_validate_json(json.dumps(draft))
        generation = repository.load(collection.collection_id)[1].generation
        with pytest.raises(CitationValidationError):
            validate_citations(
                repository,
                collection.collection_id,
                generation,
                [h for h in context if h.filename != "api.md"],
                parsed,
            )
        return
    else:
        original = generator.complete

        def changed(*args):
            raw = original(*args)
            repository.build(collection, FakeEmbedder(), RetrievalSettings())
            return raw

        generator.complete = changed
    result = ask(
        repository, collection.collection_id, "AUTH_REQUIRED", Settings(), FakeEmbedder(), generator
    )
    assert result.status == "validation_failed" and not result.claims and not result.citations
    assert len(generator.calls) == 1


@pytest.mark.parametrize(
    "draft",
    [
        "not json",
        '{"status":"answered","claims":[],"conflicts":[]}',
        '{"status":"insufficient_evidence","claims":[],"conflicts":[],"tool":"shell"}',
    ],
)
def test_malformed_model_output_is_not_shown(indexed, draft):
    repository, collection = indexed
    result = ask(
        repository,
        collection.collection_id,
        "token",
        Settings(),
        FakeEmbedder(),
        FixtureGenerator(draft),
    )
    assert result.status == "validation_failed" and not result.citations
    assert "not json" not in result.text


def test_explicit_insufficient_evidence_skips_review(indexed):
    repository, collection = indexed
    generator = FixtureGenerator({"status": "insufficient_evidence", "claims": [], "conflicts": []})
    result = ask(
        repository,
        collection.collection_id,
        "Unknown retention period?",
        Settings(),
        FakeEmbedder(),
        generator,
    )
    assert result.status == "insufficient_evidence" and len(generator.calls) == 1
    assert not result.citations


@pytest.mark.parametrize(
    "review,expected",
    [
        (
            {
                "supported_claims": [],
                "confirmed_conflicts": [],
                "question_fully_addressed": True,
                "relevant_evidence": True,
                "unresolved_conflict": False,
            },
            "validation_failed",
        ),
        (
            {
                "supported_claims": [0],
                "confirmed_conflicts": [],
                "question_fully_addressed": False,
                "relevant_evidence": True,
                "unresolved_conflict": False,
            },
            "insufficient_evidence",
        ),
        (
            {
                "supported_claims": [0],
                "confirmed_conflicts": [],
                "question_fully_addressed": True,
                "relevant_evidence": False,
                "unresolved_conflict": False,
            },
            "insufficient_evidence",
        ),
        (
            {
                "supported_claims": [0],
                "confirmed_conflicts": [],
                "question_fully_addressed": True,
                "relevant_evidence": True,
                "unresolved_conflict": True,
            },
            "validation_failed",
        ),
        (
            {
                "supported_claims": [-1],
                "confirmed_conflicts": [],
                "question_fully_addressed": True,
                "relevant_evidence": True,
                "unresolved_conflict": False,
            },
            "validation_failed",
        ),
        (
            {
                "supported_claims": [0, 0],
                "confirmed_conflicts": [],
                "question_fully_addressed": True,
                "relevant_evidence": True,
                "unresolved_conflict": False,
            },
            "validation_failed",
        ),
    ],
)
def test_separate_review_rejects_unsupported_partial_or_conflicted_answers(
    indexed, review, expected
):
    repository, collection = indexed
    result = ask(
        repository,
        collection.collection_id,
        "token and missing details?",
        Settings(),
        FakeEmbedder(),
        FixtureGenerator(claim_draft(collection), review),
    )
    assert result.status == expected and not result.claims and not result.citations


@pytest.mark.parametrize("fully_addressed", [True, False])
def test_two_source_conflict_preserves_both_quotes(indexed, fully_addressed):
    repository, collection = indexed
    a, b = collection.documents[:2]
    # Controlled model fixture tests mechanics, not genuine semantic conflict detection.
    draft = {
        "status": "conflicting_evidence",
        "claims": [],
        "conflicts": [
            {
                "issue": "Fixture disagreement.",
                "evidence": [
                    {"passage_id": a.passages[0].passage_id, "quote": a.passages[0].text},
                    {"passage_id": b.passages[0].passage_id, "quote": b.passages[0].text},
                ],
            }
        ],
    }
    review = {
        "supported_claims": [],
        "confirmed_conflicts": [0],
        "question_fully_addressed": fully_addressed,
        "relevant_evidence": True,
        "unresolved_conflict": True,
    }
    result = ask(
        repository,
        collection.collection_id,
        "token",
        Settings(),
        FakeEmbedder(),
        FixtureGenerator(draft, review),
    )
    assert result.status == "conflicting_evidence" and len(result.citations) == 2
    assert "documentation owner" in result.text
    draft["conflicts"][0]["evidence"][1] = draft["conflicts"][0]["evidence"][0]
    assert (
        ask(
            repository,
            collection.collection_id,
            "token",
            Settings(),
            FakeEmbedder(),
            FixtureGenerator(draft, review),
        ).status
        == "validation_failed"
    )


def test_unavailable_model_and_changed_model_leave_index_intact(indexed):
    repository, collection = indexed
    before = repository.load(collection.collection_id)[1]

    class Unavailable(FixtureGenerator):
        def identity(self):
            raise RetrievalError("Private server text")

    result = ask(
        repository, collection.collection_id, "token", Settings(), FakeEmbedder(), Unavailable({})
    )
    assert result.status == "generation_failed" and "Private" not in result.text
    generator = FixtureGenerator(claim_draft(collection))
    identities = iter(
        [
            GenerationIdentity(model="qwen3-vl:4b-instruct", digest="old"),
            GenerationIdentity(model="qwen3-vl:4b-instruct", digest="new"),
        ]
    )
    generator.identity = lambda: next(identities)
    assert (
        ask(
            repository, collection.collection_id, "token", Settings(), FakeEmbedder(), generator
        ).status
        == "generation_failed"
    )
    assert repository.load(collection.collection_id)[1] == before


def test_whole_passage_context_budget_and_invalid_queries(indexed):
    repository, collection = indexed
    hits = retrieve(
        repository, collection.collection_id, "token", "hybrid", RetrievalSettings(), FakeEmbedder()
    ).hits
    assert bounded_context(hits, 1) == ([], [])
    generator = FixtureGenerator({})
    for query in ("", "x" * 2001):
        assert (
            ask(
                repository, collection.collection_id, query, Settings(), FakeEmbedder(), generator
            ).status
            == "validation_failed"
        )
    assert not generator.calls


def test_local_generator_protocol_and_incomplete_response(monkeypatch):
    generator = OllamaGenerator(RetrievalSettings(), GenerationSettings())
    calls = []

    def request(path, body):
        calls.append(body)
        return {
            "model": "qwen3-vl:4b-instruct",
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": "{}"},
        }

    monkeypatch.setattr(generator.transport, "_request", request)
    assert generator.complete("Trusted system policy", {"question": "untrusted"}, {}) == "{}"
    request_body = calls[0]
    assert "tools" not in request_body and request_body["stream"] is False
    assert request_body["messages"][0]["role"] == "system" and len(request_body["messages"]) == 2
    monkeypatch.setattr(generator.transport, "_request", lambda *args: {"done": False})
    with pytest.raises(RetrievalError):
        generator.complete("policy", {}, {})


def test_answer_ui_offline_uses_inert_sources(indexed, monkeypatch):
    repository, collection = indexed
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(repository.root))
    monkeypatch.setattr(
        "knowledgebridge.embedding_adapter.OllamaEmbedder", lambda settings: FakeEmbedder()
    )
    monkeypatch.setattr(
        "knowledgebridge.answer_generator.OllamaGenerator",
        lambda *args: FixtureGenerator(claim_draft(collection)),
    )
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("No network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    at = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=45
    ).run()
    at.radio[0].set_value("Ask KnowledgeBridge").run()
    assert not at.exception
    next(w for w in at.text_input if w.label == "Question about this collection").set_value(
        "AUTH_REQUIRED"
    )
    next(w for w in at.button if w.label == "Ask using saved sources").click().run()
    assert not at.exception and any(w.value == "Status: answered" for w in at.text)
    assert any("AUTH_REQUIRED" in w.value for w in at.code)
    assert not calls


def test_no_context_does_not_invoke_generation(indexed, monkeypatch):
    from knowledgebridge.retrieval_models import RetrievalReport

    repository, collection = indexed
    report = RetrievalReport(
        mode="hybrid",
        generation=repository.load(collection.collection_id)[1].generation,
        hits=[],
        candidate_count=20,
        rrf_k=60,
        elapsed_ms=0.0,
    )
    monkeypatch.setattr("knowledgebridge.answering.retrieve", lambda *args: report)
    generator = FixtureGenerator({})
    assert (
        ask(
            repository, collection.collection_id, "token", Settings(), FakeEmbedder(), generator
        ).status
        == "insufficient_evidence"
    )
    assert not generator.calls


def test_rebuild_during_review_invalidates_otherwise_supported_answer(indexed):
    repository, collection = indexed
    generator = FixtureGenerator(claim_draft(collection))
    original = generator.complete

    def complete(*args):
        raw = original(*args)
        if len(generator.calls) == 2:
            repository.build(collection, FakeEmbedder(), RetrievalSettings())
        return raw

    generator.complete = complete
    result = ask(
        repository, collection.collection_id, "token", Settings(), FakeEmbedder(), generator
    )
    assert result.status == "validation_failed" and not result.citations


def test_reviewer_schema_failure_never_exposes_original_claim(indexed):
    repository, collection = indexed
    generator = FixtureGenerator(
        claim_draft(collection, "PRIVATE UNSUPPORTED DRAFT"), "malformed review"
    )
    result = ask(
        repository, collection.collection_id, "token", Settings(), FakeEmbedder(), generator
    )
    assert result.status == "validation_failed" and "PRIVATE" not in result.model_dump_json()


def test_context_overflow_and_token_limit_are_rejected(monkeypatch):
    generator = OllamaGenerator(RetrievalSettings(), GenerationSettings(num_ctx=8192))

    def forbidden(*args):
        raise AssertionError("Oversized input must not be sent")

    monkeypatch.setattr(generator.transport, "_request", forbidden)
    with pytest.raises(RetrievalError, match="context"):
        generator.complete("policy", {"text": "x" * 10000}, {})
    monkeypatch.setattr(
        generator.transport,
        "_request",
        lambda *args: {
            "model": "qwen3-vl:4b-instruct",
            "done": True,
            "done_reason": "length",
            "message": {"role": "assistant", "content": "{}"},
        },
    )
    with pytest.raises(RetrievalError, match="incomplete"):
        generator.complete("policy", {}, {})


def test_timeout_has_safe_reason_and_preserves_index(indexed, monkeypatch):
    from knowledgebridge.embedding_adapter import OllamaTimeoutError

    repository, collection = indexed
    before = repository.load(collection.collection_id)[1]
    generator = FixtureGenerator({})

    def timeout(*args):
        raise OllamaTimeoutError("Private runtime detail")

    generator.complete = timeout
    answer = ask(
        repository, collection.collection_id, "token", Settings(), FakeEmbedder(), generator
    )
    assert answer.status == "generation_failed" and answer.reason == "model_timeout"
    assert "Private" not in answer.model_dump_json()
    assert repository.load(collection.collection_id)[1] == before


def test_identifier_context_focus_preserves_matching_hits_and_top_complements(indexed):
    from knowledgebridge.answering import focus_context

    repository, collection = indexed
    hits = retrieve(
        repository, collection.collection_id, "token", "hybrid", RetrievalSettings(), FakeEmbedder()
    ).hits
    assert focus_context(hits, "How do credentials work?") == hits
    assert focus_context(hits, "unknown_key") == hits
    focused = focus_context(hits, "page_size")
    assert all(h in focused for h in hits[:2])
    assert any("page_size" in h.passage.text for h in focused)
