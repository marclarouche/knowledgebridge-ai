"""Explicit evaluation denominators; model self-review is never human support evidence."""

import hashlib
import json
from collections import Counter
from typing import Literal

from pydantic import Field

from knowledgebridge.answer_models import AnswerRecord
from knowledgebridge.library import LibraryManager
from knowledgebridge.models import KnowledgeCollection, Record
from knowledgebridge.retrieval_models import RetrievalError, RetrievalReport


class RelevanceTarget(Record):
    filename: str = Field(min_length=1)
    contains: str = Field(min_length=1)


class EvaluationCase(Record):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    targets: list[RelevanceTarget]
    expected_status: Literal["answered", "insufficient_evidence", "conflicting_evidence"]


class EvaluationDataset(Record):
    provenance: str
    human_authored: bool
    questions: list[EvaluationCase] = Field(min_length=1)

    def checked(self, collection: KnowledgeCollection) -> "EvaluationDataset":
        if len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Duplicate evaluation case IDs")
        for case in self.questions:
            if case.expected_status != "insufficient_evidence" and not case.targets:
                raise ValueError(f"{case.id}: supported/conflict case needs relevance targets")
            relevant_passages(collection, case)
        return self


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def relevant_passages(collection: KnowledgeCollection, case: EvaluationCase) -> set[str]:
    """Resolve every annotation to exact passage IDs, rejecting stale targets."""
    relevant: set[str] = set()
    for target in case.targets:
        matches = {
            p.passage_id
            for d in collection.documents
            if d.filename == target.filename
            for p in d.passages
            if target.contains in p.text
        }
        if not matches:
            raise ValueError(f"{case.id}: relevance target does not match the indexed corpus")
        relevant.update(matches)
    return relevant


def retrieval_score(report: RetrievalReport, relevant: set[str], k: int) -> dict[str, object]:
    if k < 1:
        raise ValueError("k must be positive")
    ids = [hit.passage.passage_id for hit in report.hits[:k]]
    if len(ids) != len(set(ids)):
        raise ValueError("Retrieval results contain duplicate passage IDs")
    found = len(set(ids) & relevant)
    return {
        "relevant_count": len(relevant),
        "retrieved_relevant": found,
        "recall_at_k": found / len(relevant) if relevant else None,
        "hit_at_k": bool(found) if relevant else None,
        "passage_ids": ids,
        "elapsed_ms": report.elapsed_ms,
    }


def citation_score(
    manager: LibraryManager, collection_id: str, answer: AnswerRecord
) -> dict[str, int]:
    """Re-resolve against current sources; check quote offsets, identity and evidence coverage."""
    valid = 0
    for citation in answer.citations:
        if answer.generation is None:
            continue
        try:
            current = manager.resolve(
                collection_id,
                citation.passage.passage_id,
                generation=answer.generation,
                quote=citation.quote,
            )
            if current == citation:
                valid += 1
        except RetrievalError:
            pass
    groups = [item.evidence for item in answer.claims] + [
        item.evidence for item in answer.conflicts
    ]
    expected = {(e.passage_id, e.quote) for group in groups for e in group}
    supplied = {(c.passage.passage_id, c.quote) for c in answer.citations}
    missing = len(expected - supplied)
    if answer.status in ("answered", "conflicting_evidence") and not expected:
        missing += 1
    return {
        "citations": len(answer.citations),
        "valid_citations": valid,
        "missing_evidence_references": missing,
    }


def rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def answer_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    """Failures stay in coverage denominators; empty citation sets are not 100% valid."""
    counts: Counter[str] = Counter()
    supported = correct_supported = unsupported = correct_abstention = false_answers = 0
    conflicts = correct_conflicts = total_citations = valid_citations = missing = 0
    for row in rows:
        expected = str(row["expected_status"])
        status = str(row["status"])
        counts[status] += 1
        total_citations += int(str(row["citations"]))
        valid_citations += int(str(row["valid_citations"]))
        missing += int(str(row["missing_evidence_references"]))
        if expected == "answered":
            supported += 1
            correct_supported += status == "answered"
        elif expected == "insufficient_evidence":
            unsupported += 1
            correct_abstention += status == "insufficient_evidence"
            false_answers += status == "answered"
        elif expected == "conflicting_evidence":
            conflicts += 1
            correct_conflicts += status == "conflicting_evidence"
    return {
        "attempted": len(rows),
        "status_counts": dict(counts),
        "supported_answer_coverage": rate(correct_supported, supported),
        "correct_abstention_rate": rate(correct_abstention, unsupported),
        "false_answer_frequency_on_unanswerable": rate(false_answers, unsupported),
        "conflict_status_rate": rate(correct_conflicts, conflicts),
        "citation_validity_rate": rate(valid_citations, total_citations),
        "missing_evidence_references": missing,
        "answer_support_accuracy": None,
        "support_note": "Requires independent human review bound to each exact answer digest; status match and same-model support checks are not support accuracy.",
    }


class HumanReview(Record):
    case_id: str
    answer_digest: str
    reviewer: str = Field(min_length=1)
    verdict: Literal["supported", "unsupported", "not_applicable"]
    rationale: str = Field(min_length=1)


def human_support_metrics(
    answers: dict[str, AnswerRecord], reviews: list[HumanReview]
) -> dict[str, object]:
    """Only exact-output reviews count; missing, stale and duplicate reviews fail closed."""
    seen: set[str] = set()
    reviewed = supported = 0
    answerable_outputs = sum(a.status == "answered" for a in answers.values())
    for review in reviews:
        if review.case_id in seen or review.case_id not in answers:
            raise ValueError("Duplicate or unknown review case")
        seen.add(review.case_id)
        answer = answers[review.case_id]
        if review.answer_digest != digest(answer.model_dump(mode="json")):
            raise ValueError("Review does not match the exact recorded answer")
        if answer.status == "answered":
            if review.verdict == "not_applicable":
                raise ValueError("An answered output needs a support verdict")
            reviewed += 1
            supported += review.verdict == "supported"
        elif review.verdict != "not_applicable":
            raise ValueError("Support accuracy measures factual answered outputs only")
    return {
        "reviewed_answer_support_accuracy": rate(supported, reviewed),
        "human_review_coverage": rate(reviewed, answerable_outputs),
        "complete": reviewed == answerable_outputs and answerable_outputs > 0,
    }
