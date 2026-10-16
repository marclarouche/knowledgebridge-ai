"""Byte-only local extraction; no URLs, filesystem extraction, macros, OCR or HTML."""

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from knowledgebridge.config import Settings
from knowledgebridge.models import DocumentFormat, ExtractionWarning


class ExtractionError(ValueError):
    """Application-owned safe diagnostic code; never store parser exception text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractedSection:
    """Extraction intermediary before assigning document/section identities."""

    text: str
    heading: str | None = None
    page: int | None = None
    decoded_start: int | None = None


@dataclass(frozen=True)
class Extraction:
    """Bounded extraction and safe limitations."""

    sections: list[ExtractedSection]
    title: str | None
    warnings: list[ExtractionWarning]


def _check(sections: list[ExtractedSection], settings: Settings) -> None:
    if (
        len(sections) > settings.max_sections
        or sum(len(s.text) for s in sections) > settings.max_extracted_chars
    ):
        raise ExtractionError("extraction_limit")


def _text(data: bytes, markdown: bool, settings: Settings) -> Extraction:
    text = data.decode("utf-8-sig")
    if "\x00" in text or text.startswith(("%PDF-", "PK\x03\x04")):
        raise ExtractionError("malformed")
    if len(text) > settings.max_extracted_chars:
        raise ExtractionError("extraction_limit")
    markers: list[tuple[int, str | None]] = [(0, None)]
    if markdown:
        position = 0
        fence: tuple[str, int] | None = None
        for line in text.splitlines(keepends=True):
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if marker:
                chars = marker.group(1)
                if fence is None:
                    fence = chars[0], len(chars)
                elif (
                    chars[0] == fence[0]
                    and len(chars) >= fence[1]
                    and not line[marker.end() :].strip()
                ):
                    fence = None
            elif fence is None:
                heading = re.match(r"^ {0,3}#{1,6}[ \t]+(.+?)\s*$", line)
                if heading:
                    label = re.sub(r"[ \t]+#+[ \t]*$", "", heading.group(1)).strip()[:500]
                    if not label:
                        position += len(line)
                        continue
                    if position == 0:
                        markers[0] = (0, label)
                    else:
                        markers.append((position, label))
                        if len(markers) > settings.max_sections + 1:
                            raise ExtractionError("extraction_limit")
            position += len(line)
    sections = [
        ExtractedSection(
            text[start : markers[i + 1][0] if i + 1 < len(markers) else len(text)],
            heading,
            decoded_start=start,
        )
        for i, (start, heading) in enumerate(markers)
        if text[start : markers[i + 1][0] if i + 1 < len(markers) else len(text)].strip()
    ]
    _check(sections, settings)
    return Extraction(sections, next((s.heading for s in sections if s.heading), None), [])


def _docx(data: bytes, settings: Settings) -> Extraction:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [i.filename for i in entries]
        if (
            len(entries) > settings.max_docx_entries
            or sum(i.file_size for i in entries) > settings.max_docx_expanded_bytes
        ):
            raise ExtractionError("container_limit")
        if len(names) != len(set(names)) or any(i.flag_bits & 1 for i in entries):
            raise ExtractionError("malformed")
        if any(
            n.startswith(("/", "\\")) or ".." in PurePosixPath(n.replace("\\", "/")).parts
            for n in names
        ):
            raise ExtractionError("malformed")
        if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
            raise ExtractionError("malformed")
        # No DTD/entity expansion, including local or external entity references.
        for item in entries:
            if item.filename.endswith((".xml", ".rels")):
                xml = archive.read(item)
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise ExtractionError("malformed")
    document = Document(io.BytesIO(data))
    sections: list[ExtractedSection] = []
    paragraphs: list[str] = []
    heading: str | None = None
    total = 0
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            value = block.text
            is_heading = block.style is not None and (
                block.style.name.startswith("Heading") or block.style.name == "Title"
            )
            if is_heading:
                if paragraphs:
                    sections.append(ExtractedSection("\n\n".join(paragraphs), heading))
                    _check(sections, settings)
                heading, paragraphs = value.strip()[:500] or None, []
        elif isinstance(block, Table):
            value = "\n".join(" | ".join(cell.text for cell in row.cells) for row in block.rows)
        else:
            continue
        total += len(value) + 2
        if total > settings.max_extracted_chars:
            raise ExtractionError("extraction_limit")
        if value.strip():
            paragraphs.append(value)
    if paragraphs:
        sections.append(ExtractedSection("\n\n".join(paragraphs), heading))
    _check(sections, settings)
    warning = ExtractionWarning(
        code="docx_limitations",
        message="DOCX body paragraphs and table cells were extracted. Tables are flattened; images, headers/footers, comments, tracked changes and embedded objects are not fully interpreted.",
    )
    title = (
        document.core_properties.title.strip()
        or next((s.heading for s in sections if s.heading), "")
    )[:500] or None
    return Extraction(sections, title, [warning])


def _pdf(data: bytes, settings: Settings) -> Extraction:
    if not data.startswith(b"%PDF-"):
        raise ExtractionError("malformed")
    # Suppress native parser diagnostics; UI diagnostics never expose document data.
    pymupdf.TOOLS.mupdf_display_errors(False)  # type: ignore[no-untyped-call]
    pymupdf.TOOLS.mupdf_display_warnings(False)  # type: ignore[no-untyped-call]
    sections: list[ExtractedSection] = []
    warnings = [
        ExtractionWarning(
            code="pdf_limitations",
            message="PDF text is extracted in page reading order. Layout, tables, diagrams, annotations and reading order may be incomplete; OCR is not performed.",
        )
    ]
    with pymupdf.open(stream=data, filetype="pdf") as document:  # type: ignore[no-untyped-call]
        if document.needs_pass:
            raise ExtractionError("encrypted_pdf")
        if document.page_count > settings.max_pdf_pages:
            raise ExtractionError("page_limit")
        for page in document:
            text = page.get_text("text", sort=True)
            if text.strip():
                sections.append(ExtractedSection(text, page=page.number + 1))
                _check(sections, settings)
            else:
                warnings.append(
                    ExtractionWarning(
                        code="no_page_text",
                        message="Page has no extractable text; images/scans require OCR, which is not supported.",
                        page=page.number + 1,
                    )
                )
        title = str((document.metadata or {}).get("title") or "").strip()[:500] or None
        if document.is_repaired:
            warnings.append(
                ExtractionWarning(
                    code="repaired_pdf",
                    message="The PDF parser repaired structural damage; verify extraction against the original.",
                )
            )
    return Extraction(sections, title, warnings)


def extract(data: bytes, format: DocumentFormat, settings: Settings) -> Extraction:
    """Extract supported content from bounded bytes, without opening source paths."""
    if format in (DocumentFormat.TXT, DocumentFormat.MARKDOWN):
        return _text(data, format == DocumentFormat.MARKDOWN, settings)
    if format == DocumentFormat.DOCX:
        return _docx(data, settings)
    return _pdf(data, settings)
