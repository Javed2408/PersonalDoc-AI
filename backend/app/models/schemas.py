"""Pydantic schemas shared by the API layer."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    version: str
    environment: str


# uploaded -> processing -> processed | failed.
# "processed" means text was extracted, chunked, embedded and stored in the vector index.
DocumentStatus = Literal["uploaded", "processing", "processed", "failed"]


class DocumentMetadata(BaseModel):
    document_id: str
    original_filename: str
    stored_filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime
    page_count: int | None = None
    chunk_count: int | None = None
    # Safe, user-facing reason when status is "failed".
    processing_error: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata]


class DocumentDeleteResponse(BaseModel):
    document_id: str
    deleted: bool


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    original_filename: str
    # Every chunk comes from exactly one page (pages are chunked independently).
    page_number: int
    # Position of the chunk within the whole document, starting at 0.
    chunk_index: int
    # Offset of the chunk's first character within its page's extracted text.
    start_char: int
    char_count: int
    text: str


class DocumentChunksResponse(BaseModel):
    document_id: str
    chunk_size: int
    chunk_overlap: int
    chunk_count: int
    chunks: list[Chunk]


DocumentId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]


class RetrievalRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    # Number of chunks to return. Omitted: the configured default (RETRIEVAL_TOP_K).
    k: int | None = Field(default=None, ge=1)
    # Omitted or empty: search every processed document.
    document_ids: list[DocumentId] | None = Field(default=None, max_length=100)

    @field_validator("document_ids")
    @classmethod
    def dedupe_document_ids(cls, value: list[str] | None) -> list[str] | None:
        return list(dict.fromkeys(value)) if value else None


class RetrievalResult(BaseModel):
    rank: int  # 1 = most similar
    chunk_id: str
    document_id: str
    original_filename: str
    page_number: int
    chunk_index: int
    start_char: int
    char_count: int
    text: str
    # Cosine distance from ChromaDB: 1 - cosine_similarity. 0 = same direction,
    # 1 = unrelated (orthogonal), 2 = opposite. Lower is more similar.
    distance: float
    # Cosine similarity: exactly 1 - distance (range -1..1). Higher is more similar.
    # A geometric measure, not a probability or confidence.
    similarity: float


class RetrievalResponse(BaseModel):
    query: str
    k: int
    # The documents searched: the requested ones, or null for all processed documents.
    document_ids: list[str] | None
    result_count: int
    results: list[RetrievalResult]
