"""Versioned document, section and passage identities for future retrieval."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ID = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=2000000)]
Label = Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=r"\S")]


def now() -> datetime:
    """Return an aware UTC timestamp, separate from stable source identities."""
    return datetime.now(UTC)


class Record(BaseModel):
    """Common strict schema; unsupported fields cannot silently become instructions."""

    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0"] = "1.0"


class DocumentFormat(StrEnum):
    """Supported extraction paths."""

    TXT = "txt"
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"


class IndexStatus(StrEnum):
    """Explicit document/collection lifecycle status."""

    NOT_INDEXED = "not_indexed"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    STALE = "stale"


class ExtractionWarning(Record):
    """Safe code/message/location, never a raw parser error or source excerpt."""

    code: str
    message: str
    severity: Literal["warning", "error"] = "warning"
    page: int | None = Field(default=None, ge=1)


class DocumentSection(Record):
    """Exact extracted text, with optional offsets into decoded TXT/Markdown."""

    section_id: ID
    document_id: ID
    document_version: Label
    heading: Label | None = None
    ordinal: int = Field(ge=0)
    page: int | None = Field(default=None, ge=1)
    text: Text
    decoded_char_start: int | None = Field(default=None, ge=0)
    decoded_char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def decoded_offsets(self) -> "DocumentSection":
        """Decoded source positions must be paired and match the exact text length."""
        if self.decoded_char_start is None:
            if self.decoded_char_end is not None:
                raise ValueError("Decoded source offsets must be paired")
        elif self.decoded_char_end != self.decoded_char_start + len(self.text):
            raise ValueError("Decoded source offsets do not match section text")
        return self


class SourceLocation(Record):
    """Half-open Unicode offsets into the referenced section, not PDF byte positions."""

    document_id: ID
    document_version: Label
    section_id: ID
    heading: Label | None = None
    page: int | None = Field(default=None, ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    offset_basis: Literal["extracted_section"] = "extracted_section"
    decoded_char_start: int | None = Field(default=None, ge=0)
    decoded_char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_range(self) -> "SourceLocation":
        """Reject reversed source spans."""
        if self.char_end <= self.char_start:
            raise ValueError("Invalid source range")
        return self


class DocumentPassage(Record):
    """A bounded exact section slice, never an embedding or generated answer."""

    passage_id: ID
    text: Text
    location: SourceLocation
    ordinal: int = Field(ge=0)
    word_count: int = Field(gt=0)
    overlap_chars: int = Field(default=0, ge=0)
    chunking_fingerprint: str


class SourceDocument(Record):
    """Parsed source metadata and its validated source-linked passages."""

    document_id: ID
    version: Label = "unspecified"
    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    title: Label
    format: DocumentFormat
    content_hash: Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
    file_size: int = Field(gt=0, le=10485760)
    imported_at: datetime = Field(default_factory=now)
    category: str | None = Field(default=None, max_length=200)
    index_status: IndexStatus = IndexStatus.NOT_INDEXED
    parser_version: Literal["extraction-1.0"] = "extraction-1.0"
    sections: list[DocumentSection] = Field(min_length=1, max_length=10000)
    passages: list[DocumentPassage] = Field(min_length=1, max_length=5000)
    warnings: list[ExtractionWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def source_links(self) -> "SourceDocument":
        """Ensure every passage resolves to its exact stored source excerpt."""
        sections = {s.section_id: s for s in self.sections}
        if len(sections) != len(self.sections) or not sections:
            raise ValueError("Sections must have unique identifiers")
        if len({p.passage_id for p in self.passages}) != len(self.passages):
            raise ValueError("Passages must have unique identifiers")
        for section in self.sections:
            if section.document_id != self.document_id or section.document_version != self.version:
                raise ValueError("Section source identity mismatch")
        for passage in self.passages:
            loc = passage.location
            passage_section = sections.get(loc.section_id)
            if (
                passage_section is None
                or loc.document_id != self.document_id
                or loc.document_version != self.version
                or loc.page != passage_section.page
                or loc.heading != passage_section.heading
                or loc.char_end > len(passage_section.text)
                or passage_section.text[loc.char_start : loc.char_end] != passage.text
            ):
                raise ValueError("Passage source reference does not resolve")
            base = passage_section.decoded_char_start
            if (
                loc.decoded_char_start != (base + loc.char_start if base is not None else None)
                or loc.decoded_char_end != (base + loc.char_end if base is not None else None)
                or passage.word_count != len(re.findall(r"\S+", passage.text))
            ):
                raise ValueError("Passage offsets or word count do not match its source")
        return self


class KnowledgeCollection(Record):
    """Collection source snapshot; content hashes are unique within this boundary."""

    collection_id: ID = Field(default_factory=lambda: str(uuid4()))
    title: Label
    created_at: datetime = Field(default_factory=now)
    modified_at: datetime = Field(default_factory=now)
    index_status: IndexStatus = IndexStatus.NOT_INDEXED
    documents: list[SourceDocument] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_documents(self) -> "KnowledgeCollection":
        """Reject ambiguous duplicate identities or byte content."""
        if len({d.content_hash for d in self.documents}) != len(self.documents) or len(
            {d.document_id for d in self.documents}
        ) != len(self.documents):
            raise ValueError("Duplicate documents")
        return self


class ImportResult(Record):
    """One file succeeds atomically or returns safe warnings with no document."""

    document: SourceDocument | None = None
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    accepted: bool = False

    @model_validator(mode="after")
    def consistent_result(self) -> "ImportResult":
        """An accepted result must contain a source document."""
        if self.accepted != (self.document is not None):
            raise ValueError("Import outcome mismatch")
        return self
