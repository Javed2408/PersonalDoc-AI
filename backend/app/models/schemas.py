"""Pydantic schemas shared by the API layer."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_name: str
    version: str
    environment: str


# Upload/storage state only. Processing states arrive with ingestion in later phases.
DocumentStatus = Literal["uploaded", "failed"]


class DocumentMetadata(BaseModel):
    document_id: str
    original_filename: str
    stored_filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata]


class DocumentDeleteResponse(BaseModel):
    document_id: str
    deleted: bool
