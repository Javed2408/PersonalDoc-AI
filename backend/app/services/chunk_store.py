"""Persistent document chunks: one JSON file per document.

The canonical record of a document's chunks; the vector store holds their embeddings.
"""

import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.models.schemas import Chunk
from app.services.json_files import write_json_atomic

logger = logging.getLogger(__name__)

_DOCUMENT_ID = re.compile(r"^[0-9a-f]{32}$")


class ChunkStoreError(Exception):
    """Chunks could not be read or written."""


class StoredChunks(BaseModel):
    document_id: str
    chunk_size: int
    chunk_overlap: int
    chunks: list[Chunk]


class JsonChunkStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, stored: StoredChunks) -> None:
        try:
            write_json_atomic(self._path(stored.document_id), stored.model_dump(mode="json"))
        except OSError as error:
            logger.error("Could not write chunks for %s: %s", stored.document_id, error)
            raise ChunkStoreError("Chunks could not be saved") from error

    def load(self, document_id: str) -> StoredChunks | None:
        path = self._path(document_id)
        try:
            return StoredChunks.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, ValidationError) as error:
            logger.error("Could not read chunks for %s: %s", document_id, error)
            raise ChunkStoreError("Chunks could not be read") from error

    def delete(self, document_id: str) -> None:
        try:
            self._path(document_id).unlink(missing_ok=True)
        except OSError as error:
            logger.error("Could not delete chunks for %s: %s", document_id, error)
            raise ChunkStoreError("Chunks could not be deleted") from error

    def _path(self, document_id: str) -> Path:
        # IDs come from our own metadata, but never build a path from an unchecked string.
        if not _DOCUMENT_ID.match(document_id):
            raise ChunkStoreError("Invalid document ID")
        return self._directory / f"{document_id}.json"
