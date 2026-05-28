from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


def _health_payload() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        openai_enabled=bool(settings.openai_api_key and settings.openai_enabled),
    )


@router.get("/")
def root() -> dict[str, str | bool]:
    health = _health_payload()
    return {
        "service": "Realist API",
        "status": health.status,
        "environment": health.environment,
        "openai_enabled": health.openai_enabled,
        "health": "/health",
        "docs": "/docs",
        "api": "/api/v1",
    }


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return _health_payload()
