"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import documents, health, retrieval
from app.config import Settings, get_settings
from app.retrieval.embeddings import Embedder, SentenceTransformerEmbedder
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import ChromaVectorStore
from app.services.chunk_store import JsonChunkStore
from app.services.document_service import DocumentService
from app.services.document_store import JsonDocumentStore
from app.services.indexing_service import DocumentIndexer
from app.services.processing_service import DocumentProcessor

UPLOAD_PATH = "/api/documents/upload"
# Allowance for multipart boundaries and headers on top of the file itself.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    # The model loads lazily on first use, so building the app stays cheap.
    embedder = embedder or SentenceTransformerEmbedder(
        settings.embedding_model, settings.embedding_device, settings.embedding_batch_size
    )
    store = JsonDocumentStore(settings.metadata_file)
    chunk_store = JsonChunkStore(settings.chunks_dir)
    vector_store = ChromaVectorStore(settings.chroma_dir, settings.chroma_collection, embedder.model_name)
    indexer = DocumentIndexer(embedder, vector_store, settings.embedding_batch_size)
    document_service = DocumentService(settings, store, chunk_store, vector_store)
    processor = DocumentProcessor(settings, store, chunk_store, document_service, vector_store, indexer)
    # Shares the embedder (one model in memory) and the vector store (one ChromaDB client).
    retriever = Retriever(
        embedder, vector_store, store,
        default_k=settings.retrieval_top_k,
        max_k=settings.retrieval_max_k,
        max_distance=settings.retrieval_max_distance,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        document_service.ensure_storage()
        # Fail fast on a broken or mismatched vector store instead of on the first upload.
        vector_store.open()
        processor.resume_pending()
        yield
        processor.shutdown()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.state.document_service = document_service
    app.state.document_processor = processor
    app.state.vector_store = vector_store
    app.state.retriever = retriever
    app.dependency_overrides[get_settings] = lambda: settings

    @app.middleware("http")
    async def reject_oversized_uploads(request: Request, call_next):
        # Reject before the multipart body is parsed and spooled to disk. The service
        # still enforces the exact limit while streaming, for requests without a length.
        if request.method == "POST" and request.url.path == UPLOAD_PATH:
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES:
                # Read and discard the body first. Responding mid-upload makes the server
                # close the connection, which proxies and browsers report as a network
                # error instead of delivering the 413.
                async for _ in request.stream():
                    pass
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"The file is larger than the {settings.max_upload_size_mb} MB limit."},
                )
        return await call_next(request)

    # Added last so it wraps everything, including the size guard's 413 responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(retrieval.router, prefix="/api")
    return app


app = create_app()
