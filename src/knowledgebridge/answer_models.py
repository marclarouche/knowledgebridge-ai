"""Bounded drafts, independent support review and application-owned answer records."""

from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from knowledgebridge.models import DocumentPassage, Record

AnswerStatus = Literal[
    "answered",
    "insufficient_evidence",
    "conflicting_evidence",
    "validation_failed",
    "generation_failed",
]


class EvidenceRef(Record):
    passage_id: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=2000)


class DraftClaim(Record):
    text: str = Field(min_length=1, max_length=1200)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=4)


class DraftConflict(Record):
    issue: str = Field(min_length=1, max_length=800)
    evidence: list[EvidenceRef] = Field(min_length=2, max_length=4)


class DraftAnswer(Record):
    status: Literal["answered", "insufficient_evidence", "conflicting_evidence"]
    claims: list[DraftClaim] = Field(max_length=6)
    conflicts: list[DraftConflict] = Field(max_length=3)

    @model_validator(mode="after")
    def consistent(self) -> "DraftAnswer":
        if (
            self.status == "answered"
            and (not self.claims or self.conflicts)
            or self.status == "insufficient_evidence"
            and (self.claims or self.conflicts)
            or self.status == "conflicting_evidence"
            and (self.claims or not self.conflicts)
        ):
            raise ValueError("Draft status and evidence disagree")
        return self


class SupportReview(Record):
    supported_claims: list[int] = Field(max_length=6)
    confirmed_conflicts: list[int] = Field(max_length=3)
    question_fully_addressed: bool
    relevant_evidence: bool
    unresolved_conflict: bool


class GenerationIdentity(Record):
    model: str = Field(min_length=1, max_length=200)
    digest: str = Field(min_length=1, max_length=200)
    adapter_version: Literal["ollama-chat-1"] = "ollama-chat-1"


class Citation(Record):
    passage: DocumentPassage
    title: str
    filename: str
    content_hash: str
    quote: str
    quote_start: int
    quote_end: int


class AnswerRecord(Record):
    answer_id: str = Field(default_factory=lambda: str(uuid4()))
    status: AnswerStatus
    text: str
    claims: list[DraftClaim] = Field(default_factory=list)
    conflicts: list[DraftConflict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    generation: str | None = None
    model: GenerationIdentity | None = None
    support_review: SupportReview | None = None
    reason: str
    review_required: Literal[True] = True
    context_passages: int = 0
    omitted_passages: int = 0
    elapsed_ms: float = 0
    prompt_version: Literal["grounded-4", "grounded-5"] = "grounded-5"
