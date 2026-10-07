"""Document upload, storage, deletion and access to processed chunks.

Uploaded files are stored as `<document_id>.pdf` inside the documents directory.
The client-supplied filename is kept for display only and never used as a path.
"""

import logging
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.config import Settings
from app.models.schemas import DocumentMetadata
from app.services.chunk_store import ChunkStoreError, JsonChunkStore, StoredChunks
from app.services.document_store import DocumentStoreError, JsonDocumentStore

logger = logging.getLogger(__name__)

PDF_EXTENSION = ".pdf"
PDF_FILE_TYPE = "pdf"
# Browsers and OSes are inconsistent here; the PDF signature check is the real gate.
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream", ""}
# The PDF spec allows the %PDF- header to appear anywhere in the first 1024 bytes.
PDF_SIGNATURE = b"%PDF-"
SIGNATURE_WINDOW = 1024
MAX_DISPLAY_NAME_LENGTH = 200
READ_BLOCK_SIZE = 1024 * 1024


class DocumentError(Exception):
    """Base class for errors with a safe, user-facing message."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentValidationError(DocumentError):
    pass


class UnsupportedFileTypeError(DocumentValidationError):
    pass


class FileTooLargeError(DocumentValidationError):
    pass


class DocumentNotFoundError(DocumentError):
    pass


class DocumentStorageError(DocumentError):
    pass


class DocumentNotProcessedError(DocumentError):
    pass


def sanitize_display_name(filename: str | None) -> str:
    """Reduce a client-supplied filename to a safe display name (never used as a path)."""
    name = (filename or "").replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    if len(name) > MAX_DISPLAY_NAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        name = f"{stem[: MAX_DISPLAY_NAME_LENGTH - len(ext) - 1]}.{ext}" if dot else name[:MAX_DISPLAY_NAME_LENGTH]
    return name


class DocumentService:
    def __init__(
        self,
        settings: Settings,
        store: JsonDocumentStore | None = None,
        chunk_store: JsonChunkStore | None = None,
    ) -> None:
        self._documents_dir = settings.documents_dir
        self._chunks_dir = settings.chunks_dir
        self._max_bytes = settings.max_upload_bytes
        self._max_mb = settings.max_upload_size_mb
        self._store = store or JsonDocumentStore(settings.metadata_file)
        self._chunk_store = chunk_store or JsonChunkStore(settings.chunks_dir)

    def ensure_storage(self) -> None:
        self._documents_dir.mkdir(parents=True, exist_ok=True)
        self._chunks_dir.mkdir(parents=True, exist_ok=True)

    def list_documents(self) -> list[DocumentMetadata]:
        try:
            documents = self._store.list()
        except DocumentStoreError as error:
            raise DocumentStorageError("The document library could not be loaded.") from error
        # The store keeps insertion order; use it to break ties between uploads that
        # landed within the same clock tick.
        ordered = sorted(enumerate(documents), key=lambda item: (item[1].created_at, item[0]), reverse=True)
        return [doc for _, doc in ordered]

    def save_upload(self, filename: str | None, content_type: str | None, source: BinaryIO) -> DocumentMetadata:
        display_name = sanitize_display_name(filename)
        if not display_name.lower().endswith(PDF_EXTENSION):
            raise UnsupportedFileTypeError("Only PDF files are supported.")
        if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError("Only PDF files are supported.")

        self.ensure_storage()
        document_id = uuid.uuid4().hex
        stored_filename = f"{document_id}{PDF_EXTENSION}"
        destination = self.stored_path(stored_filename)
        partial = destination.with_name(f".{stored_filename}.part")

        try:
            file_size = self._copy_validated(source, partial)
            partial.replace(destination)
        except DocumentValidationError:
            partial.unlink(missing_ok=True)
            raise
        except OSError as error:
            partial.unlink(missing_ok=True)
            logger.error("Failed to store upload %s: %s", document_id, error)
            raise DocumentStorageError("The file could not be saved.") from error

        document = DocumentMetadata(
            document_id=document_id,
            original_filename=display_name,
            stored_filename=stored_filename,
            file_type=PDF_FILE_TYPE,
            file_size=file_size,
            status="uploaded",
            created_at=datetime.now(UTC),
        )
        try:
            self._store.add(document)
        except DocumentStoreError as error:
            # Don't leave an orphaned file the library can't see.
            destination.unlink(missing_ok=True)
            raise DocumentStorageError("The file could not be saved.") from error

        logger.info("Stored document %s (%d bytes)", document_id, file_size)
        return document

    def delete_document(self, document_id: str) -> None:
        try:
            document = self._store.get(document_id)
        except DocumentStoreError as error:
            raise DocumentStorageError("The document library could not be loaded.") from error
        if document is None:
            raise DocumentNotFoundError("Document not found.")

        path = self.stored_path(document.stored_filename)
        try:
            path.unlink()
        except FileNotFoundError:
            logger.warning("File for document %s was already missing; removing metadata", document_id)
        except OSError as error:
            logger.error("Failed to delete file for document %s: %s", document_id, error)
            raise DocumentStorageError("The document could not be deleted.") from error

        try:
            self._chunk_store.delete(document_id)
            self._store.remove(document_id)
        except (ChunkStoreError, DocumentStoreError) as error:
            raise DocumentStorageError("The document could not be deleted.") from error
        logger.info("Deleted document %s", document_id)

    def get_chunks(self, document_id: str) -> StoredChunks:
        try:
            document = self._store.get(document_id)
        except DocumentStoreError as error:
            raise DocumentStorageError("The document library could not be loaded.") from error
        if document is None:
            raise DocumentNotFoundError("Document not found.")
        if document.status == "failed":
            raise DocumentNotProcessedError("This document could not be processed, so it has no text chunks.")
        if document.status != "processed":
            raise DocumentNotProcessedError("This document has not finished processing yet.")

        try:
            stored = self._chunk_store.load(document_id)
        except ChunkStoreError as error:
            raise DocumentStorageError("The document's text chunks could not be loaded.") from error
        if stored is None:
            logger.error("Chunks file missing for processed document %s", document_id)
            raise DocumentStorageError("The document's text chunks are missing.")
        return stored

    def _copy_validated(self, source: BinaryIO, destination: Path) -> int:
        """Stream `source` to `destination`, enforcing the size limit and PDF signature."""
        total = 0
        head = b""
        with destination.open("xb") as out:
            while block := source.read(READ_BLOCK_SIZE):
                total += len(block)
                if total > self._max_bytes:
                    raise FileTooLargeError(f"The file is larger than the {self._max_mb} MB limit.")
                if len(head) < SIGNATURE_WINDOW:
                    head += block[: SIGNATURE_WINDOW - len(head)]
                out.write(block)

        if total == 0:
            raise DocumentValidationError("The file is empty.")
        if PDF_SIGNATURE not in head:
            raise UnsupportedFileTypeError("The file does not appear to be a valid PDF.")
        return total

    def stored_path(self, stored_filename: str) -> Path:
        """Resolve a stored filename, refusing anything that escapes the documents directory."""
        base = self._documents_dir.resolve()
        path = (base / stored_filename).resolve()
        if path.parent != base:
            raise DocumentStorageError("Invalid document path.")
        return path
