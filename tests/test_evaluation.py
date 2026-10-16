"""Evaluation regression tests prevent inflated metrics and stale review credit."""

import json
from pathlib import Path

import pytest
from test_answering import FixtureGenerator, claim_draft
from test_retrieval import FakeEmbedder

from knowledgebridge.answering import ask
from knowledgebridge.config import RetrievalSettings, Settings
from knowledgebridge.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    HumanReview,
    answer_metrics,
    citation_score,
    digest,
    human_support_metrics,
    relevant_passages,
    retrieval_score,
)
from knowledgebridge.index_repository import IndexRepository
from knowledgebridge.library import LibraryManager
from knowledgebridge.retriever import retrieve

pytest_plugins = ["test_retrieval"]


def test_recall_counts_all_relevant_passages_and_not_just_one_hit(tmp_path, collection):
    repo = IndexRepository(tmp_path / "index")
    repo.build(collection, FakeEmbedder(), RetrievalSettings())
    report = retrieve(repo, collection.collection_id, "token", "keyword", RetrievalSettings())
    first = report.hits[0].passage.passage_id
    score = retrieval_score(report, {first, "another-relevant-passage"}, 1)
    assert score["recall_at_k"] == 0.5 and score["hit_at_k"] is True
    assert retrieval_score(report, set(), 5)["recall_at_k"] is None
    duplicated = report.model_copy(update={"hits": [report.hits[0], report.hits[0]]})
    with pytest.raises(ValueError, match="duplicate"):
        retrieval_score(duplicated, {first}, 5)


def test_dataset_checks_stale_targets_and_duplicate_ids(collection):
    case = EvaluationCase(
        id="1",
        category="supported",
        question="token",
        expected_status="answered",
        targets=[{"filename": "api.md", "contains": "AUTH_REQUIRED"}],
    )
    assert relevant_passages(collection, case)
    dataset = EvaluationDataset(provenance="test", human_authored=False, questions=[case])
    assert dataset.checked(collection) == dataset
    with pytest.raises(ValueError, match="Duplicate"):
        dataset.model_copy(update={"questions": [case, case]}).checked(collection)
    with pytest.raises(ValueError, match="does not match"):
        relevant_passages(
            collection,
            case.model_copy(
                update={
                    "targets": [case.targets[0].model_copy(update={"contains": "not in corpus"})]
                }
            ),
        )
    with pytest.raises(ValueError, match="needs relevance"):
        dataset.model_copy(update={"questions": [case.model_copy(update={"targets": []})]}).checked(
            collection
        )


def test_service_failures_never_count_as_correct_abstentions():
    rows = [
        {
            "expected_status": "insufficient_evidence",
            "status": status,
            "citations": 0,
            "valid_citations": 0,
            "missing_evidence_references": 0,
        }
        for status in (
            "answered",
            "insufficient_evidence",
            "generation_failed",
            "validation_failed",
        )
    ]
    metrics = answer_metrics(rows)
    assert metrics["correct_abstention_rate"]["rate"] == 0.25
    assert metrics["false_answer_frequency_on_unanswerable"]["rate"] == 0.25
    assert metrics["citation_validity_rate"]["rate"] is None
    assert metrics["answer_support_accuracy"] is None
    assert answer_metrics([])["supported_answer_coverage"]["rate"] is None


def test_citation_evaluation_detects_metadata_tampering_and_retired_generations(
    tmp_path, collection
):
    repo = IndexRepository(tmp_path / "index")
    repo.build(collection, FakeEmbedder(), RetrievalSettings())
    answer = ask(
        repo,
        collection.collection_id,
        "AUTH_REQUIRED",
        Settings(),
        FakeEmbedder(),
        FixtureGenerator(claim_draft(collection)),
    )
    manager = LibraryManager(repo)
    assert citation_score(manager, collection.collection_id, answer)["valid_citations"] == 1
    modified = answer.model_copy(deep=True)
    modified.citations[0].filename = "invented.txt"
    assert citation_score(manager, collection.collection_id, modified)["valid_citations"] == 0
    modified.citations = []
    assert (
        citation_score(manager, collection.collection_id, modified)["missing_evidence_references"]
        == 1
    )
    repo.build(collection, FakeEmbedder(), RetrievalSettings())
    assert citation_score(manager, collection.collection_id, answer)["valid_citations"] == 0


def test_human_support_requires_exact_reviewed_output_and_complete_coverage(tmp_path, collection):
    repo = IndexRepository(tmp_path / "index")
    repo.build(collection, FakeEmbedder(), RetrievalSettings())
    answer = ask(
        repo,
        collection.collection_id,
        "AUTH_REQUIRED",
        Settings(),
        FakeEmbedder(),
        FixtureGenerator(claim_draft(collection)),
    )
    answers = {"case": answer}
    review = HumanReview(
        case_id="case",
        answer_digest=digest(answer.model_dump(mode="json")),
        reviewer="Test reviewer fixture",
        verdict="supported",
        rationale="Fixture only",
    )
    assert human_support_metrics(answers, [])["complete"] is False
    assert human_support_metrics(answers, [review])["complete"] is True
    assert human_support_metrics(answers, [review])["reviewed_answer_support_accuracy"]["rate"] == 1
    with pytest.raises(ValueError, match="exact"):
        human_support_metrics(answers, [review.model_copy(update={"answer_digest": "stale"})])
    with pytest.raises(ValueError, match="Duplicate"):
        human_support_metrics(answers, [review, review])
    with pytest.raises(ValueError, match="verdict"):
        human_support_metrics(answers, [review.model_copy(update={"verdict": "not_applicable"})])


def test_development_dataset_is_explicitly_not_human_authored():
    path = Path(__file__).resolve().parents[1] / "samples/fleetops_demo/evaluation_questions.json"
    dataset = EvaluationDataset.model_validate(json.loads(path.read_text()))
    assert not dataset.human_authored and len(dataset.questions) >= 30
    assert {"exact", "paraphrase", "unsupported", "conflict", "partial", "injection"} <= {
        q.category for q in dataset.questions
    }


def test_human_review_cli_roundtrip_and_no_overwrite(tmp_path, collection):
    import os
    import subprocess
    import sys

    from knowledgebridge.answer_models import AnswerRecord

    answer = AnswerRecord(status="answered", text="Fixture answer", reason="fixture")
    payload = {
        "complete": True,
        "answers": [
            {
                "id": "case",
                "answer": answer.model_dump(mode="json"),
                "answer_digest": digest(answer.model_dump(mode="json")),
            }
        ],
    }
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(json.dumps(payload))
    worksheet = tmp_path / "worksheet.json"
    output = tmp_path / "scores.json"
    script = Path(__file__).resolve().parents[1] / "scripts/score_human_reviews.py"

    def run(*extra):
        return subprocess.run(
            [sys.executable, str(script), "--evaluation", str(evaluation), *extra],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(script.parents[1] / "src")},
            timeout=20,
        )

    assert run("--output", str(worksheet)).returncode == 0
    assert run("--output", str(worksheet)).returncode != 0
    reviews = json.loads(worksheet.read_text())
    reviews[0].update(reviewer="Test fixture only", verdict="supported", rationale="CLI fixture")
    worksheet.write_text(json.dumps(reviews))
    assert run("--reviews", str(worksheet), "--output", str(output)).returncode == 0
    assert json.loads(output.read_text())["complete"] is True
