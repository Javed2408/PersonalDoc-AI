"""Background document processing: extract text, chunk it, embed it, store the vectors.

Status flow: uploaded -> processing -> processed | failed. "processed" is only set once
the vectors are in the vector store. Jobs run one at a time on a single worker thread so
CPU-heavy extraction and embedding never block request handling.
"""

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait

from app.config import Settings
from app.ingestion.loader import ExtractionError
from app.ingestion.pipeline import process_pdf
from app.ingestion.splitter import RecursiveTextSplitter
from app.retrieval.embeddings import EmbeddingError
from app.retrieval.vector_store import ChromaVectorStore, VectorStoreError
from app.services.chunk_store import ChunkStoreError, JsonChunkStore, StoredChunks
from app.services.document_service import DocumentService, DocumentStorageError
from app.services.document_store import DocumentStoreError, JsonDocumentStore
from app.services.indexing_service import DocumentIndexer, IndexingCancelled

logger = logging.getLogger(__name__)

PENDING_STATUSES = {"uploaded", "processing"}
GENERIC_FAILURE = "The document could not be processed."
VECTOR_STORE_FAILURE = "The document could not be saved to the vector index. Check the backend logs."


class DocumentProcessor:
    def __init__(
        self,
        settings: Settings,
        store: JsonDocumentStore,
        chunk_store: JsonChunkStore,
        documents: DocumentService,
        vector_store: ChromaVectorStore,
        indexer: DocumentIndexer,
    ) -> None:
        self._store = store
        self._chunk_store = chunk_store
        self._documents = documents
        self._vector_store = vector_store
        self._indexer = indexer
        self._splitter = RecursiveTextSplitter(settings.chunk_size, settings.chunk_overlap)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="document-processing")
        self._pending: set[Future] = set()
        self._pending_lock = threading.Lock()

    def submit(self, document_id: str) -> None:
        future = self._executor.submit(self._run, document_id)
        with self._pending_lock:
            self._pending.add(future)
        future.add_done_callback(self._forget)

    def resume_pending(self) -> None:
        """Re-queue interrupted documents, and processed ones whose vectors are missing.

        The second case covers documents processed before vectors existed (Phase 3), a
        deleted or new ChromaDB collection, and crashes between storing and recording.
        """
        try:
            documents = self._store.list()
        except DocumentStoreError:
            logger.error("Could not check for unprocessed documents at startup")
            return
        for document in sorted(documents, key=lambda doc: doc.created_at):
            if document.status in PENDING_STATUSES:
                self.submit(document.document_id)
            elif document.status == "processed" and not self._vectors_complete(document):
                logger.warning("Document %s is missing vectors; re-indexing", document.document_id)
                self.submit(document.document_id)

    def _vectors_complete(self, document) -> bool:
        try:
            return self._vector_store.count_document(document.document_id) == document.chunk_count
        except VectorStoreError:
            return False

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        """Block until every queued job has finished. Returns False on timeout."""
        with self._pending_lock:
            pending = set(self._pending)
        _, not_done = wait(pending, timeout=timeout)
        return not not_done

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _forget(self, future: Future) -> None:
        with self._pending_lock:
            self._pending.discard(future)

    def _run(self, document_id: str) -> None:
        try:
            self._process(document_id)
        except Exception:  # noqa: BLE001
            # Last line of defence for a background thread: anything unexpected is logged
            # and recorded on the document instead of vanishing inside the Future.
            logger.exception("Unexpected error while processing document %s", document_id)
            self._fail(document_id, GENERIC_FAILURE)

    def _process(self, document_id: str) -> None:
        document = self._store.update(document_id, status="processing", processing_error=None)
        if document is None:
            return  # Deleted before its turn came.

        logger.info("Processing document %s", document_id)
        try:
            path = self._documents.stored_path(document.stored_filename)
            result = process_pdf(path, document_id, document.original_filename, self._splitter)
        except (ExtractionError, DocumentStorageError) as error:
            logger.warning("Processing failed for document %s: %s", document_id, error.message)
            self._fail(document_id, error.message)
            return

        try:
            self._chunk_store.save(
                StoredChunks(
                    document_id=document_id,
                    chunk_size=self._splitter.chunk_size,
                    chunk_overlap=self._splitter.chunk_overlap,
                    chunks=result.chunks,
                )
            )
        except ChunkStoreError:
            self._fail(document_id, "The extracted text could not be saved.")
            return

        try:
            self._indexer.index(
                document_id, result.chunks, is_cancelled=lambda: self._store.get(document_id) is None
            )
        except IndexingCancelled:
            logger.info("Document %s was deleted during indexing; cleaning up", document_id)
            self._discard(document_id)
            return
        except EmbeddingError as error:
            # Chunks are valid and kept; only the vectors are missing.
            self._fail(document_id, error.message, keep_chunks=True)
            return
        except VectorStoreError:
            self._fail(document_id, VECTOR_STORE_FAILURE, keep_chunks=True)
            return

        updated = self._store.update(
            document_id,
            status="processed",
            page_count=result.page_count,
            chunk_count=len(result.chunks),
            processing_error=None,
        )
        if updated is None:
            # Deleted while we were working: don't leave orphaned chunks or vectors behind.
            self._discard(document_id)
            return
        logger.info(
            "Processed document %s: %d pages, %d chunks", document_id, result.page_count, len(result.chunks)
        )

    def _fail(self, document_id: str, message: str, keep_chunks: bool = False) -> None:
        # Never leave a partial set of vectors that could later be mistaken for a full index.
        try:
            self._vector_store.delete_document(document_id)
        except VectorStoreError:
            logger.error("Could not remove partial vectors for document %s", document_id)
        try:
            if not keep_chunks:
                self._chunk_store.delete(document_id)
            self._store.update(document_id, status="failed", processing_error=message, chunk_count=None)
        except (ChunkStoreError, DocumentStoreError):
            logger.error("Could not record processing failure for document %s", document_id)

    def _discard(self, document_id: str) -> None:
        try:
            self._vector_store.delete_document(document_id)
            self._chunk_store.delete(document_id)
        except (VectorStoreError, ChunkStoreError):
            logger.error("Could not clean up after deleted document %s", document_id)
