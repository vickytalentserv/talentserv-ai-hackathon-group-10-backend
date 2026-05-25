from pathlib import Path

from fastapi import Header, HTTPException, status

from app.config import settings


def verify_ingest_api_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    if settings.ingest_api_key:
        if x_admin_key != settings.ingest_api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing X-Admin-Key header",
            )
        return

    if settings.app_env != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="INGEST_API_KEY must be configured outside development",
        )
