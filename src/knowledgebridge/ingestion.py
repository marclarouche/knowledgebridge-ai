"""Atomic bounded import; originals are never written or opened by source name."""

import hashlib
import re
from pathlib import PurePosixPath
from uuid import NAMESPACE_URL, uuid5

from knowledgebridge.chunker import chunk_sections
from knowledgebridge.config import Settings
from knowledgebridge.models import (
    DocumentFormat,
    DocumentSection,
    ExtractionWarning,
    ImportResult,
    KnowledgeCollection,
    SourceDocument,
    now,
)
from knowledgebridge.parsers import ExtractionError, extract

MESSAGES = {
    "file_size": "File exceeds the configured byte limit (at most 10 MiB).",
    "empty": "No usable text was extracted. Empty and image-only documents are not imported.",
    "unsupported": "Choose a TXT, Markdown (.md/.markdown), DOCX or text-based PDF file.",
    "malformed": "Unable to parse this file. Check its format, encoding and structure.",
    "encrypted_pdf": "Password-protected PDFs are not supported. Provide an authorized unencrypted copy.",
    "extraction_limit": "Extracted text or section count exceeded the configured limits; nothing imported.",
    "container_limit": "DOCX archive entries or expanded size exceeded configured limits; nothing imported.",
    "page_limit": "PDF page count exceeded the configured limit; nothing imported.",
    "passage_limit": "Generated passage count exceeded the configured limit; nothing imported.",
    "collection_limit": "Collection document, extracted-text or passage limits would be exceeded.",
    "duplicate": "Identical file bytes are already present in this collection; duplicate skipped.",
    "metadata": "Check the filename, title, version and category metadata limits.",
}
FORMATS = {
    ".txt": DocumentFormat.TXT,
    ".md": DocumentFormat.MARKDOWN,
    ".markdown": DocumentFormat.MARKDOWN,
    ".docx": DocumentFormat.DOCX,
    ".pdf": DocumentFormat.PDF,
}


def failure(code: str) -> ImportResult:
    """Return a generic diagnostic without raw input or parser exception text."""
    return ImportResult(
        warnings=[ExtractionWarning(code=code, message=MESSAGES[code], severity="error")]
    )


def import_document(
    data: bytes,
    filename: str,
    settings: Settings,
    *,
    existing: KnowledgeCollection | None = None,
    version: str = "unspecified",
    title: str | None = None,
    category: str | None = None,
) -> ImportResult:
    """Parse, chunk and validate one bounded file atomically, without mutating a collection."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name or len(name) > 255 or any(ord(c) < 32 for c in name):
        return failure("metadata")
    format = FORMATS.get(PurePosixPath(name).suffix.lower())
    if format is None:
        return failure("unsupported")
    if len(data) > settings.max_file_bytes:
        return failure("file_size")
    if not data:
        return failure("empty")
    if (
        not version.strip()
        or len(version) > 500
        or (title is not None and (not title.strip() or len(title) > 500))
        or (category is not None and len(category) > 200)
    ):
        return failure("metadata")
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    prior = existing.documents if existing is not None else []
    if any(d.content_hash == digest for d in prior):
        return failure("duplicate")
    if len(prior) >= settings.max_documents:
        return failure("collection_limit")
    document_id = str(uuid5(NAMESPACE_URL, "knowledgebridge:" + digest))
    try:
        extracted = extract(data, format, settings)
        if not extracted.sections:
            result = failure("empty")
            result.warnings = extracted.warnings + result.warnings
            return result
        sections = [
            DocumentSection(
                section_id=str(uuid5(NAMESPACE_URL, f"{document_id}:{version}:extraction-1.0:{i}")),
                document_id=document_id,
                document_version=version,
                ordinal=i,
                text=s.text,
                heading=s.heading,
                page=s.page,
                decoded_char_start=s.decoded_start,
                decoded_char_end=s.decoded_start + len(s.text)
                if s.decoded_start is not None
                else None,
            )
            for i, s in enumerate(extracted.sections)
        ]
    except ExtractionError as error:
        return failure(error.code)
    except Exception:  # noqa: BLE001 — third-party parsing is an untrusted-input boundary
        # Third-party parsers expose many input-dependent exception types.
        # Never display/log their message; existing collection state is untouched.
        return failure("malformed")
    try:
        passages = chunk_sections(
            sections, settings.chunking, max_passages=settings.max_passages_per_document
        )
    except ValueError:
        return failure("passage_limit")
    if (
        sum(len(s.text) for d in prior for s in d.sections) + sum(len(s.text) for s in sections)
        > settings.max_collection_chars
        or sum(len(d.passages) for d in prior) + len(passages) > settings.max_collection_passages
    ):
        return failure("collection_limit")
    warnings = list(extracted.warnings)
    if any(
        len(m.group()) > settings.chunking.max_chars
        for s in sections
        for m in re.finditer(r"\S+", s.text)
    ):
        warnings.append(
            ExtractionWarning(
                code="long_token_split",
                message="An oversized unbroken token was split at the character limit; inspect its passages before future retrieval.",
            )
        )
    document = SourceDocument(
        document_id=document_id,
        version=version,
        filename=name,
        title=title or extracted.title or PurePosixPath(name).stem,
        format=format,
        content_hash=digest,
        file_size=len(data),
        category=category,
        sections=sections,
        passages=passages,
        warnings=warnings,
    )
    return ImportResult(document=document, accepted=True, warnings=warnings)


def ingest(
    collection: KnowledgeCollection,
    data: bytes,
    filename: str,
    settings: Settings,
    *,
    version: str = "unspecified",
    title: str | None = None,
    category: str | None = None,
) -> tuple[KnowledgeCollection, ImportResult]:
    """Return a new collection on success, or the original unchanged after failure."""
    result = import_document(
        data,
        filename,
        settings,
        existing=collection,
        version=version,
        title=title,
        category=category,
    )
    if result.document is None:
        return collection, result
    updated = KnowledgeCollection.model_validate_json(collection.model_dump_json())
    updated.documents.append(result.document)
    updated.modified_at = now()
    return updated, result
