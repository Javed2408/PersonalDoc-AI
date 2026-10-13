"""Document upload, listing, deletion, retrying failed processing, chunk inspection and PDF preview."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.models.schemas import (
    DocumentChunksResponse,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentMetadata,
)
from app.services.document_service import (
    DocumentError,
    DocumentNotFoundError,
    DocumentService,
    DocumentStateError,
    DocumentStorageError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from app.services.processing_service import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(request: Request) -> DocumentService:
    return request.app.state.document_service


def get_document_processor(request: Request) -> DocumentProcessor:
    return request.app.state.document_processor


def to_http_error(error: DocumentError) -> HTTPException:
    if isinstance(error, DocumentNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, DocumentStateError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, FileTooLargeError):
        code = status.HTTP_413_CONTENT_TOO_LARGE
    elif isinstance(error, UnsupportedFileTypeError):
        code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    elif isinstance(error, DocumentStorageError):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=error.message)


@router.get("", response_model=DocumentListResponse)
def list_documents(service: DocumentService = Depends(get_document_service)) -> DocumentListResponse:
    try:
        return DocumentListResponse(documents=service.list_documents())
    except DocumentError as error:
        raise to_http_error(error) from error


@router.post("/upload", response_model=DocumentMetadata, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> DocumentMetadata:
    try:
        document = service.save_upload(file.filename, file.content_type, file.file)
    except DocumentError as error:
        raise to_http_error(error) from error
    finally:
        file.file.close()
    # Extraction and chunking run in the background; clients poll the list for status.
    processor.submit(document.document_id)
    return document


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentChunksResponse:
    try:
        stored = service.get_chunks(document_id)
    except DocumentError as error:
        raise to_http_error(error) from error
    return DocumentChunksResponse(
        document_id=stored.document_id,
        chunk_size=stored.chunk_size,
        chunk_overlap=stored.chunk_overlap,
        chunk_count=len(stored.chunks),
        chunks=stored.chunks,
    )


# Only real document IDs: anything else (including "../" tricks) is rejected before any lookup.
DocumentIdPath = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]

PDF_RESPONSE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    # Private documents: never kept in the browser's disk cache.
    "Cache-Control": "no-store",
    # Other sites can't embed the file. (No CSP sandbox: it stops browsers' built-in PDF viewers.)
    "Cross-Origin-Resource-Policy": "same-site",
}


@router.get("/{document_id}/file", response_class=FileResponse)
def get_document_file(
    document_id: DocumentIdPath,
    service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    """The original PDF, shown inline by the browser's own viewer (which understands #page=N)."""
    try:
        document, path = service.get_file(document_id)
    except DocumentError as error:
        raise to_http_error(error) from error
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.original_filename,
        content_disposition_type="inline",
        headers=PDF_RESPONSE_HEADERS,
    )


@router.post("/{document_id}/reindex", response_model=DocumentMetadata, status_code=status.HTTP_202_ACCEPTED)
def reindex_document(
    document_id: DocumentIdPath,
    processor: DocumentProcessor = Depends(get_document_processor),
) -> DocumentMetadata:
    """Process a failed document again, under the same ID. Clients poll the list for the result.

    Only failed documents: anything queued, processing or processed gets 409.
    """
    try:
        return processor.retry_failed(document_id)
    except DocumentError as error:
        raise to_http_error(error) from error


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentDeleteResponse:
    try:
        service.delete_document(document_id)
    except DocumentError as error:
        raise to_http_error(error) from error
    return DocumentDeleteResponse(document_id=document_id, deleted=True)
