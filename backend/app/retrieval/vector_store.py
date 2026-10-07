"""Persistent vector storage in ChromaDB.

Stores and removes chunk vectors and reports on what is stored. Querying for
similar chunks belongs to the retriever (Phase 5), not here.
"""

import logging
import threading
from collections.abc import Sequence
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import ChromaError

from app.models.schemas import Chunk

logger = logging.getLogger(__name__)

MODEL_METADATA_KEY = "embedding_model"


class VectorStoreError(Exception):
    """The vector store could not complete an operation."""


class EmbeddingModelMismatchError(VectorStoreError):
    """The collection was built with a different embedding model than the one configured."""


def chunk_metadata(chunk: Chunk) -> dict[str, str | int]:
    """Provenance stored with every vector; everything except the text itself."""
    return {
        "document_id": chunk.document_id,
        "original_filename": chunk.original_filename,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "start_char": chunk.start_char,
        "char_count": chunk.char_count,
    }


class ChromaVectorStore:
    def __init__(self, path: Path, collection_name: str, embedding_model: str) -> None:
        self._path = path
        self._collection_name = collection_name
        self._embedding_model = embedding_model
        self._client = None
        self._collection = None
        self._lock = threading.Lock()

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def open(self) -> None:
        """Connect to (or create) the persistent collection. Safe to call repeatedly."""
        self._get_collection()

    def upsert_chunks(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        """Insert or replace vectors keyed by chunk_id, so repeats never create duplicates."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        collection = self._get_collection()
        step = self._client.get_max_batch_size()
        try:
            for start in range(0, len(chunks), step):
                batch = chunks[start:start + step]
                collection.upsert(
                    ids=[chunk.chunk_id for chunk in batch],
                    embeddings=[list(vector) for vector in embeddings[start:start + step]],
                    documents=[chunk.text for chunk in batch],
                    metadatas=[chunk_metadata(chunk) for chunk in batch],
                )
        except (ChromaError, ValueError) as error:
            logger.error("Could not store %d vectors: %s", len(chunks), error)
            raise VectorStoreError("Vectors could not be stored") from error

    def get_document_records(self, document_id: str) -> dict[str, tuple[str, dict]]:
        """Existing records for a document: chunk_id -> (text, metadata)."""
        try:
            result = self._get_collection().get(
                where={"document_id": document_id}, include=["documents", "metadatas"]
            )
        except ChromaError as error:
            logger.error("Could not read vectors for %s: %s", document_id, error)
            raise VectorStoreError("Vectors could not be read") from error
        return {
            chunk_id: (text, metadata)
            for chunk_id, text, metadata in zip(result["ids"], result["documents"], result["metadatas"])
        }

    def count_document(self, document_id: str) -> int:
        try:
            result = self._get_collection().get(where={"document_id": document_id}, include=[])
        except ChromaError as error:
            logger.error("Could not count vectors for %s: %s", document_id, error)
            raise VectorStoreError("Vectors could not be read") from error
        return len(result["ids"])

    def has_document(self, document_id: str) -> bool:
        return self.count_document(document_id) > 0

    def delete_ids(self, chunk_ids: Sequence[str]) -> None:
        if not chunk_ids:
            return
        try:
            self._get_collection().delete(ids=list(chunk_ids))
        except ChromaError as error:
            logger.error("Could not delete %d vectors: %s", len(chunk_ids), error)
            raise VectorStoreError("Vectors could not be deleted") from error

    def delete_document(self, document_id: str) -> None:
        """Remove every vector of a document. A document with no vectors is fine."""
        try:
            self._get_collection().delete(where={"document_id": document_id})
        except ChromaError as error:
            logger.error("Could not delete vectors for %s: %s", document_id, error)
            raise VectorStoreError("Vectors could not be deleted") from error

    def stats(self) -> dict[str, str | int]:
        collection = self._get_collection()
        try:
            count = collection.count()
        except ChromaError as error:
            raise VectorStoreError("Vector statistics are unavailable") from error
        return {
            "collection": self._collection_name,
            "embedding_model": self._embedding_model,
            "vector_count": count,
        }

    def _get_collection(self):
        with self._lock:
            if self._collection is not None:
                return self._collection
            try:
                self._path.mkdir(parents=True, exist_ok=True)
                # Telemetry off: nothing about the user's library leaves the machine.
                self._client = chromadb.PersistentClient(
                    path=str(self._path), settings=ChromaSettings(anonymized_telemetry=False)
                )
                collection = self._client.get_or_create_collection(
                    name=self._collection_name,
                    embedding_function=None,  # We always supply our own embeddings.
                    configuration={"hnsw": {"space": "cosine"}},
                    metadata={MODEL_METADATA_KEY: self._embedding_model},
                )
            except (ChromaError, OSError, ValueError) as error:
                logger.error("Could not open ChromaDB at %s: %s", self._path, error)
                raise VectorStoreError("The vector store could not be opened") from error

            # get_or_create ignores metadata for an existing collection, so check it ourselves:
            # vectors from different models are not comparable and must never be mixed.
            stored_model = (collection.metadata or {}).get(MODEL_METADATA_KEY)
            if stored_model != self._embedding_model:
                raise EmbeddingModelMismatchError(
                    f"ChromaDB collection '{self._collection_name}' at {self._path} was built with "
                    f"embedding model '{stored_model}', but EMBEDDING_MODEL is '{self._embedding_model}'. "
                    "Use a new CHROMA_COLLECTION (documents will be re-indexed on startup) or switch "
                    "EMBEDDING_MODEL back."
                )
            self._collection = collection
            logger.info(
                "Vector store ready: collection '%s' (%d vectors)", self._collection_name, collection.count()
            )
            return collection
