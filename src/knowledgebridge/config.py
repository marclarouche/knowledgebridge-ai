"""Bounded safe YAML settings, without executable patterns or source-driven paths."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChunkSettings(BaseModel):
    """Starting passage limits; these are not empirically optimized settings."""

    model_config = ConfigDict(extra="forbid", strict=True)
    max_words: int = Field(default=500, ge=1, le=2000)
    max_chars: int = Field(default=4000, ge=32, le=20000)
    overlap_words: int = Field(default=50, ge=0, le=500)

    @model_validator(mode="after")
    def bounded_overlap(self) -> "ChunkSettings":
        """Require forward progress even for short windows."""
        if self.overlap_words >= self.max_words:
            raise ValueError("Overlap must be smaller than the word limit")
        return self


class RetrievalSettings(BaseModel):
    """Local model and bounded ranking settings; no source-controlled network paths."""

    model_config = ConfigDict(extra="forbid", strict=True)
    model: str = Field(default="embeddinggemma:latest", min_length=1, max_length=200)
    host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=11434, ge=1, le=65535)
    timeout_seconds: int = Field(default=120, ge=1, le=300)
    batch_size: int = Field(default=8, ge=1, le=16)
    candidate_count: int = Field(default=20, ge=1, le=100)
    top_k: int = Field(default=5, ge=1, le=20)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    max_query_chars: int = Field(default=2000, ge=1, le=4000)


class GenerationSettings(BaseModel):
    """Generation budgets; no similarity threshold is treated as evidence proof."""

    model_config = ConfigDict(extra="forbid", strict=True)
    model: str = Field(default="qwen3-vl:4b-instruct", min_length=1, max_length=200)
    timeout_seconds: int = Field(default=240, ge=1, le=300)
    context_passages: int = Field(default=12, ge=1, le=20)
    max_context_chars: int = Field(default=18000, ge=1000, le=24000)
    max_output_chars: int = Field(default=24000, ge=1000, le=48000)
    num_ctx: int = Field(default=32768, ge=8192, le=32768)
    num_predict: int = Field(default=2048, ge=256, le=4096)


class Settings(BaseModel):
    """User-adjustable limits with fixed hard ceilings."""

    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0"] = "1.0"
    max_file_bytes: int = Field(default=10485760, ge=1, le=10485760)
    max_documents: int = Field(default=100, ge=1, le=1000)
    max_extracted_chars: int = Field(default=1000000, ge=1, le=2000000)
    max_collection_chars: int = Field(default=10000000, ge=1, le=20000000)
    max_sections: int = Field(default=2000, ge=1, le=10000)
    max_pdf_pages: int = Field(default=500, ge=1, le=1000)
    max_docx_entries: int = Field(default=2000, ge=1, le=5000)
    max_docx_expanded_bytes: int = Field(default=41943040, ge=1, le=52428800)
    max_passages_per_document: int = Field(default=2000, ge=1, le=5000)
    max_collection_passages: int = Field(default=10000, ge=1, le=50000)
    chunking: ChunkSettings = Field(default_factory=ChunkSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)


def load_settings(path: Path) -> Settings:
    """Load at most 32 KiB of local configuration using SafeLoader."""
    with path.open("rb") as handle:
        data = handle.read(32769)
    if len(data) > 32768:
        raise ValueError("Configuration exceeds its size limit")
    return Settings.model_validate(yaml.safe_load(data.decode("utf-8")))
