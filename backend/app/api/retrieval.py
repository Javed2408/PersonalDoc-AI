"""Retrieval endpoint: returns the most relevant chunks for a question (no answer generation)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.models.schemas import RetrievalRequest, RetrievalResponse
from app.retrieval.retriever import (
    DocumentsNotSearchableError,
    InvalidRetrievalRequest,
    RetrievalError,
    Retriever,
    UnknownDocumentsError,
)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


def get_retriever(request: Request) -> Retriever:
    return request.app.state.retriever


def to_http_error(error: RetrievalError) -> HTTPException:
    if isinstance(error, InvalidRetrievalRequest):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    elif isinstance(error, UnknownDocumentsError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, DocumentsNotSearchableError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=code, detail=error.message)


@router.post("/search", response_model=RetrievalResponse)
def search(body: RetrievalRequest, retriever: Retriever = Depends(get_retriever)) -> RetrievalResponse:
    k = body.k if body.k is not None else retriever.default_k
    try:
        results = retriever.search(body.query, k=k, document_ids=body.document_ids)
    except RetrievalError as error:
        raise to_http_error(error) from error
    return RetrievalResponse(
        query=body.query,
        k=k,
        document_ids=body.document_ids,
        result_count=len(results),
        results=results,
    )
