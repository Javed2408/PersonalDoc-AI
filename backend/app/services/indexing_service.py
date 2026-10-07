"""Chunks -> embeddings -> vector store, without duplicates or needless re-embedding.

For a document, compare the new chunks with the vectors already stored:
  - same chunk_id, text and metadata: keep (no re-embedding)
  - new or changed chunk: embed and upsert (chunk_id is the vector ID)
  - stored vector whose chunk no longer exists: delete
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.models.schemas import Chunk
from app.retrieval.embeddings import Embedder
from app.retrieval.vector_store import ChromaVectorStore, chunk_metadata

logger = logging.getLogger(__name__)


class IndexingCancelled(Exception):
    """The document disappeared (was deleted) while it was being indexed."""


@dataclass(frozen=True)
class IndexResult:
    embedded: int  # New or changed chunks that were embedded and stored
    unchanged: int  # Chunks already stored with identical content
    removed: int  # Stale vectors deleted


class DocumentIndexer:
    def __init__(self, embedder: Embedder, vector_store: ChromaVectorStore, batch_size: int) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._batch_size = batch_size

    def index(
        self,
        document_id: str,
        chunks: Sequence[Chunk],
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> IndexResult:
        if any(chunk.document_id != document_id for chunk in chunks):
            raise ValueError("All chunks must belong to the document being indexed")

        existing = self._vector_store.get_document_records(document_id)
        wanted = {chunk.chunk_id for chunk in chunks}
        to_embed = [
            chunk for chunk in chunks
            if existing.get(chunk.chunk_id) != (chunk.text, chunk_metadata(chunk))
        ]
        stale = [chunk_id for chunk_id in existing if chunk_id not in wanted]

        # Embed and store batch by batch, so a deleted document stops early and a
        # crash leaves only complete batches behind (picked up again on restart).
        for start in range(0, len(to_embed), self._batch_size):
            if is_cancelled():
                raise IndexingCancelled(document_id)
            batch = to_embed[start:start + self._batch_size]
            vectors = self._embedder.embed([chunk.text for chunk in batch])
            self._vector_store.upsert_chunks(batch, vectors)

        self._vector_store.delete_ids(stale)
        result = IndexResult(embedded=len(to_embed), unchanged=len(chunks) - len(to_embed), removed=len(stale))
        logger.info(
            "Indexed document %s: %d embedded, %d unchanged, %d stale removed",
            document_id, result.embedded, result.unchanged, result.removed,
        )
        return result
