"""Health check endpoint: the backend itself, plus whether the local LLM can answer."""

from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.models.schemas import HealthResponse, LLMHealth

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request, settings: Settings = Depends(get_settings)) -> HealthResponse:
    llm = request.app.state.llm
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        llm=LLMHealth(status=llm.status(), model=llm.model_name),
    )
