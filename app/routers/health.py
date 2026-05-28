from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Realist API",
        "health": "/health",
        "docs": "/docs",
    }


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        openai_enabled=bool(settings.openai_api_key and settings.openai_enabled),
    )
