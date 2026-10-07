"""Document upload, listing and deletion endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.models.schemas import DocumentDeleteResponse, DocumentListResponse, DocumentMetadata
from app.services.document_service import (
    DocumentError,
    DocumentNotFoundError,
    DocumentService,
    DocumentStorageError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(request: Request) -> DocumentService:
    return request.app.state.document_service


def to_http_error(error: DocumentError) -> HTTPException:
    if isinstance(error, DocumentNotFoundError):
        code = status.HTTP_404_NOT_FOUND
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
) -> DocumentMetadata:
    try:
        return service.save_upload(file.filename, file.content_type, file.file)
    except DocumentError as error:
        raise to_http_error(error) from error
    finally:
        file.file.close()


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
