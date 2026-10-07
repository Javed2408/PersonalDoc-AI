"""Question -> most relevant chunks. Retrieval only: nothing here generates answers.

    question --(one embedding)--> query vector --(one ChromaDB query)--> top-k chunks

Only documents with status "processed" are searched. Their vectors are complete,
whereas a document still being indexed may have partial vectors, and stale vectors
should never surface.
"""

import logging
from collections.abc import Sequence

from app.models.schemas import RetrievalResult
from app.retrieval.embeddings import Embedder, EmbeddingError
from app.retrieval.vector_store import ChromaVectorStore, VectorStoreError
from app.services.document_store import DocumentStoreError, JsonDocumentStore

logger = logging.getLogger(__name__)

MAX_COSINE_DISTANCE = 2.0


def clamp_distance(distance: float) -> float:
    """Keep float32 rounding (e.g. -2e-7 for an identical vector) inside the valid 0..2 range."""
    return min(max(distance, 0.0), MAX_COSINE_DISTANCE)


class RetrievalError(Exception):
    """Base class; `message` is safe to show to users."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRetrievalRequest(RetrievalError):
    pass


class UnknownDocumentsError(RetrievalError):
    pass


class DocumentsNotSearchableError(RetrievalError):
    pass


class RetrievalUnavailableError(RetrievalError):
    pass


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        vector_store: ChromaVectorStore,
        documents: JsonDocumentStore,
        default_k: int,
        max_k: int,
        max_distance: float | None = None,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._documents = documents
        self.default_k = default_k
        self.max_k = max_k
        self._max_distance = max_distance

    def search(
        self, query: str, k: int | None = None, document_ids: Sequence[str] | None = None
    ) -> list[RetrievalResult]:
        query = (query or "").strip()
        if not query:
            raise InvalidRetrievalRequest("The query must not be empty.")
        k = self.default_k if k is None else k
        if not 1 <= k <= self.max_k:
            raise InvalidRetrievalRequest(f"k must be between 1 and {self.max_k}.")

        searchable = self._searchable_documents(document_ids)
        if not searchable:
            logger.info("Retrieval: k=%d, no processed documents to search", k)
            return []

        try:
            [embedding] = self._embedder.embed([query])
            hits = self._vector_store.query_nearest(embedding, k, searchable)
        except EmbeddingError as error:
            raise RetrievalUnavailableError("The embedding model is unavailable. Check the backend logs.") from error
        except VectorStoreError as error:
            raise RetrievalUnavailableError("The vector index could not be searched. Check the backend logs.") from error

        hits = [(clamp_distance(hit.distance), hit) for hit in hits]
        # Stable order: by distance, then chunk_id, so equally distant chunks don't swap
        # places between runs (the ANN index returns ties in arbitrary order).
        hits.sort(key=lambda item: (item[0], item[1].chunk_id))
        if self._max_distance is not None:
            hits = [(distance, hit) for distance, hit in hits if distance <= self._max_distance]

        results = [
            RetrievalResult(
                rank=rank,
                chunk_id=hit.chunk_id,
                document_id=hit.metadata["document_id"],
                original_filename=hit.metadata["original_filename"],
                page_number=hit.metadata["page_number"],
                chunk_index=hit.metadata["chunk_index"],
                start_char=hit.metadata["start_char"],
                char_count=hit.metadata["char_count"],
                text=hit.text,
                distance=distance,
                similarity=1.0 - distance,
            )
            for rank, (distance, hit) in enumerate(hits, start=1)
        ]
        self._log(query, k, document_ids, results)
        return results

    def _searchable_documents(self, document_ids: Sequence[str] | None) -> list[str]:
        try:
            documents = {doc.document_id: doc for doc in self._documents.list()}
        except DocumentStoreError as error:
            raise RetrievalUnavailableError("The document library could not be loaded.") from error

        if not document_ids:
            return sorted(doc_id for doc_id, doc in documents.items() if doc.status == "processed")

        requested = list(dict.fromkeys(document_ids))
        unknown = [doc_id for doc_id in requested if doc_id not in documents]
        if unknown:
            raise UnknownDocumentsError(f"Unknown document ID(s): {', '.join(unknown)}.")
        not_ready = [doc_id for doc_id in requested if documents[doc_id].status != "processed"]
        if not_ready:
            details = ", ".join(f"{documents[d].original_filename} ({documents[d].status})" for d in not_ready)
            raise DocumentsNotSearchableError(f"These documents are not processed, so they can't be searched: {details}.")
        return requested

    @staticmethod
    def _log(query: str, k: int, document_ids, results: list[RetrievalResult]) -> None:
        # INFO: shape of the search only. The query text and per-result details are DEBUG,
        # because questions and documents may be private (Rules.md: privacy).
        logger.info(
            "Retrieval: k=%d, filter=%s, results=%d, best_distance=%s",
            k,
            f"{len(document_ids)} document(s)" if document_ids else "all",
            len(results),
            f"{results[0].distance:.4f}" if results else "n/a",
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Retrieval query (%d chars): %r", len(query), query)
            for result in results:
                logger.debug(
                    "  #%d distance=%.4f %s p.%d chunk %d (%s)",
                    result.rank, result.distance, result.original_filename,
                    result.page_number, result.chunk_index, result.chunk_id,
                )
