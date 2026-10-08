"""Grounded question answering over the user's documents. One independent request per question."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.retrieval import to_http_error as retrieval_http_error
from app.generation.llm import LLMError, LLMModelNotFoundError, LLMTimeoutError, LLMUnavailableError
from app.generation.rag_chain import RagChain
from app.models.schemas import ChatRequest, ChatResponse
from app.retrieval.retriever import RetrievalError

router = APIRouter(tags=["chat"])


def get_rag_chain(request: Request) -> RagChain:
    return request.app.state.rag_chain


def llm_http_error(error: LLMError) -> HTTPException:
    if isinstance(error, (LLMUnavailableError, LLMModelNotFoundError)):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(error, LLMTimeoutError):
        code = status.HTTP_504_GATEWAY_TIMEOUT
    else:
        code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=code, detail=error.message)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, rag: RagChain = Depends(get_rag_chain)) -> ChatResponse:
    try:
        result = rag.answer(body.question, k=body.k, document_ids=body.document_ids)
    except RetrievalError as error:
        raise retrieval_http_error(error) from error
    except LLMError as error:
        raise llm_http_error(error) from error
    return ChatResponse(
        question=body.question,
        answer=result.answer,
        status=result.status,
        model=result.model,
        sources=result.sources,
    )
