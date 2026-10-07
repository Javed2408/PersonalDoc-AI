"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import documents, health
from app.config import Settings, get_settings
from app.services.document_service import DocumentService

UPLOAD_PATH = "/api/documents/upload"
# Allowance for multipart boundaries and headers on top of the file itself.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    document_service = DocumentService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        document_service.ensure_storage()
        yield

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.state.document_service = document_service
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
    return app


app = create_app()
