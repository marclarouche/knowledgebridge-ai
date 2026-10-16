"""Reproducible section-local windows with bounded overlap and source offsets."""

import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid5

from knowledgebridge.config import ChunkSettings
from knowledgebridge.models import DocumentPassage, DocumentSection, SourceLocation

CHUNKER_VERSION = "section-window-1.0"


def chunk_sections(
    sections: list[DocumentSection], settings: ChunkSettings, *, max_passages: int
) -> list[DocumentPassage]:
    """Prefer paragraph boundaries, split long paragraphs/tokens, never cross a section.

    A window is an exact half-open slice. Overlap is capped by words; it is omitted
    when it would repeat a whole short window or prevent forward progress.
    """
    fingerprint = hashlib.sha256(
        json.dumps(
            {"version": CHUNKER_VERSION, "settings": settings.model_dump()}, sort_keys=True
        ).encode()
    ).hexdigest()
    passages: list[DocumentPassage] = []
    for section in sections:
        text = section.text
        paragraphs = [m.end() for m in re.finditer(r"\r?\n[ \t]*\r?\n", text)]
        start, previous_end = 0, 0
        while start < len(text):
            end = min(len(text), start + settings.max_chars)
            words = list(re.finditer(r"\S+", text[start:end]))
            if len(words) > settings.max_words:
                end = start + words[settings.max_words].start()
            if end < len(text):
                boundaries = [p for p in paragraphs if previous_end < p <= end and p > start]
                if boundaries:
                    end = boundaries[-1]
                elif (
                    text[end : end + 1]
                    and not text[end - 1 : end].isspace()
                    and not text[end : end + 1].isspace()
                ):
                    spaces = list(re.finditer(r"\s+", text[start:end]))
                    if spaces and start + spaces[-1].end() > previous_end:
                        end = start + spaces[-1].end()
            if end <= previous_end:
                start = previous_end
                continue
            excerpt = text[start:end]
            if excerpt.strip():
                if len(passages) >= max_passages:
                    raise ValueError("Passage limit exceeded")
                identity = json.dumps(
                    [
                        section.document_id,
                        section.document_version,
                        section.section_id,
                        fingerprint,
                        start,
                        end,
                    ],
                    ensure_ascii=False,
                )
                base = section.decoded_char_start
                passages.append(
                    DocumentPassage(
                        passage_id=str(uuid5(NAMESPACE_URL, identity)),
                        text=excerpt,
                        location=SourceLocation(
                            document_id=section.document_id,
                            document_version=section.document_version,
                            section_id=section.section_id,
                            heading=section.heading,
                            page=section.page,
                            char_start=start,
                            char_end=end,
                            decoded_char_start=base + start if base is not None else None,
                            decoded_char_end=base + end if base is not None else None,
                        ),
                        ordinal=len(passages),
                        word_count=len(re.findall(r"\S+", excerpt)),
                        overlap_chars=max(0, previous_end - start),
                        chunking_fingerprint=fingerprint,
                    )
                )
            if end == len(text):
                break
            tail = list(re.finditer(r"\S+", excerpt))
            next_start = (
                start + tail[-settings.overlap_words].start()
                if settings.overlap_words and len(tail) > settings.overlap_words
                else end
            )
            previous_end = end
            start = next_start if next_start > start else end
    return passages
