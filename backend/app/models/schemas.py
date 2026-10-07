"""Pydantic schemas shared by the API layer."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    version: str
    environment: str


# uploaded -> processing -> processed | failed.
# "processed" means text was extracted and chunked; it does not imply embeddings exist.
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
