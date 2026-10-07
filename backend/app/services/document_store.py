"""Persistent document metadata, stored as a single JSON file.

Kept behind a small interface so it can be swapped for SQLite or similar later.
Assumes a single backend process; the lock serialises writes between request threads.
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path

from pydantic import ValidationError

from app.models.schemas import DocumentMetadata

logger = logging.getLogger(__name__)


class DocumentStoreError(Exception):
    """The metadata file could not be read or written."""


class JsonDocumentStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def list(self) -> list[DocumentMetadata]:
        with self._lock:
            return list(self._read().values())

    def get(self, document_id: str) -> DocumentMetadata | None:
        with self._lock:
            return self._read().get(document_id)

    def add(self, document: DocumentMetadata) -> None:
        with self._lock:
            documents = self._read()
            if document.document_id in documents:
                raise DocumentStoreError(f"Document {document.document_id} already exists")
            documents[document.document_id] = document
            self._write(documents)

    def remove(self, document_id: str) -> None:
        with self._lock:
            documents = self._read()
            if documents.pop(document_id, None) is not None:
                self._write(documents)

    def _read(self) -> dict[str, DocumentMetadata]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            documents = [DocumentMetadata.model_validate(item) for item in raw["documents"]]
        except (OSError, ValueError, KeyError, TypeError, ValidationError) as error:
            # Never overwrite an unreadable file: that would silently lose every record.
            logger.error("Could not read document metadata at %s: %s", self._path, error)
            raise DocumentStoreError("Document metadata is unreadable") from error
        return {document.document_id: document for document in documents}

    def _write(self, documents: dict[str, DocumentMetadata]) -> None:
        payload = {"documents": [doc.model_dump(mode="json") for doc in documents.values()]}
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Write to a temp file and rename so a crash never leaves a half-written file.
            fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    json.dump(payload, tmp, indent=2)
                os.replace(tmp_name, self._path)
            except BaseException:
                Path(tmp_name).unlink(missing_ok=True)
                raise
        except OSError as error:
            logger.error("Could not write document metadata at %s: %s", self._path, error)
            raise DocumentStoreError("Document metadata could not be saved") from error
