"""Passage limits/coverage, architecture separation and complete offline UI tour."""

import ast
import itertools
import random
import re
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from knowledgebridge.chunker import chunk_sections
from knowledgebridge.config import ChunkSettings, Settings
from knowledgebridge.ingestion import import_document
from knowledgebridge.models import DocumentSection, SourceDocument

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_ui_data(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOWLEDGEBRIDGE_DATA_DIR", str(tmp_path / "ui-index"))


def section(text):
    return DocumentSection(
        section_id="SEC-1",
        document_id="DOC-1",
        document_version="2.0",
        heading="Section heading",
        ordinal=0,
        text=text,
    )


def test_paragraph_boundaries_and_exact_coverage():
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph ends."
    settings = ChunkSettings(max_chars=48, max_words=100, overlap_words=0)
    passages = chunk_sections([section(text)], settings, max_passages=10)
    assert passages[0].text.endswith("\n\n")
    assert "".join(p.text for p in passages) == text
    assert all(p.location.heading == "Section heading" for p in passages)
    assert len({p.passage_id for p in passages}) == len(passages)


def test_overlap_is_bounded_and_never_repeats_whole_window():
    text = " ".join(f"word{i}" for i in range(30))
    settings = ChunkSettings(max_chars=1000, max_words=5, overlap_words=2)
    passages = chunk_sections([section(text)], settings, max_passages=100)
    for previous, current in itertools.pairwise(passages):
        overlap = text[current.location.char_start : previous.location.char_end]
        assert len(re.findall(r"\S+", overlap)) <= 2
        assert current.location.char_end > previous.location.char_end
        assert current.location.char_start > previous.location.char_start
    assert all(p.word_count <= 5 and p.overlap_chars < len(p.text) for p in passages)
    assert passages == chunk_sections([section(text)], settings, max_passages=100)
    other = chunk_sections(
        [section(text)], settings.model_copy(update={"overlap_words": 1}), max_passages=100
    )
    assert passages[0].passage_id != other[0].passage_id


def test_long_token_split_and_limit_failure():
    result = import_document(
        b"x" * 200,
        "long.txt",
        Settings(chunking=ChunkSettings(max_chars=32, max_words=10, overlap_words=0)),
    )
    assert result.accepted
    assert all(len(p.text) <= 32 for p in result.document.passages)
    assert "".join(p.text for p in result.document.passages) == "x" * 200
    assert any(w.code == "long_token_split" for w in result.warnings)
    with pytest.raises(ValueError, match="Passage limit"):
        chunk_sections([section("x" * 200)], ChunkSettings(max_chars=32), max_passages=1)


def test_seeded_chunking_edge_cases_coverage_and_forward_progress():
    randomizer = random.Random(31)
    for _ in range(100):
        text = "".join(
            randomizer.choice(["alpha", "βeta", "🛠", " ", "\n\n", "\r\n", "x" * 80, "\t"])
            for _ in range(100)
        )
        configured = ChunkSettings(
            max_chars=randomizer.choice([32, 65, 128]),
            max_words=10,
            overlap_words=randomizer.choice([0, 1, 3]),
        )
        passages = chunk_sections([section(text)], configured, max_passages=1000)
        coverage = set()
        previous_end = 0
        for p in passages:
            loc = p.location
            assert p.text == text[loc.char_start : loc.char_end]
            assert len(p.text) <= configured.max_chars and p.word_count <= configured.max_words
            assert loc.char_end > previous_end
            coverage.update(range(loc.char_start, loc.char_end))
            previous_end = loc.char_end
        assert all(index in coverage for index, char in enumerate(text) if not char.isspace())


def test_section_and_page_boundaries_are_not_crossed():
    a = section("First section. " * 20)
    b = a.model_copy(update={"section_id": "SEC-2", "page": 2, "text": "Second page text. " * 20})
    passages = chunk_sections([a, b], ChunkSettings(max_chars=64), max_passages=100)
    assert all((p.location.section_id == "SEC-1") == (p.location.page is None) for p in passages)
    assert next(p for p in passages if p.location.section_id == "SEC-2").overlap_chars == 0


def test_forged_passage_reference_fails_validation():
    document = import_document(b"A real source paragraph", "a.txt", Settings()).document
    data = document.model_dump(mode="json")
    data["passages"][0]["text"] = "Invented source excerpt"
    with pytest.raises(ValueError):
        SourceDocument.model_validate_json(__import__("json").dumps(data))


def widget(at, kind, label):
    return next(item for item in getattr(at, kind) if item.label == label)


def test_ui_collection_demo_and_all_inspection_views_offline(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("No network permitted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    assert not at.exception
    widget(at, "text_input", "Collection title").set_value("My collection")
    widget(at, "button", "Create collection").click().run()
    assert len(at.session_state.collections) == 1
    widget(at, "button", "Load FleetOps Demo collection").click().run()
    assert not at.exception
    assert len(at.session_state.collections) == 2
    demo = next(c for c in at.session_state.collections if c.title == "FleetOps Demo — fictional")
    assert len(demo.documents) == 8
    widget(at, "button", "Load FleetOps Demo collection").click().run()
    assert not at.exception
    assert (
        len(next(c for c in at.session_state.collections if c.title == demo.title).documents) == 8
    )
    for view in [
        "Parsed Documents",
        "Passage Explorer",
        "Document Import",
        "Settings and Diagnostics",
    ]:
        widget(at, "radio", "View").set_value(view).run()
        assert not at.exception
        if view == "Passage Explorer":
            assert at.code
    assert not calls


def test_ui_empty_collection_is_clear_and_has_no_chat():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    widget(at, "radio", "View").set_value("Passage Explorer").run()
    assert not at.exception and at.info
    assert not at.get("chat_input")


def test_engine_has_no_streamlit_or_execution_imports():
    for path in (ROOT / "src/knowledgebridge").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(
                    n.name.split(".")[0] not in {"streamlit", "subprocess", "requests"}
                    for n in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in {
                    "streamlit",
                    "subprocess",
                    "requests",
                }
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec"}
