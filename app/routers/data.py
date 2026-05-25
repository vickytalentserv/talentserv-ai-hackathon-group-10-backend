from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.admin import verify_ingest_api_key
from app.config import settings
from app.database import get_db
from app.schemas import IngestFileResult, IngestResponse
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.post("/ingest", response_model=IngestResponse)
def ingest_fallback_data(
    _: None = Depends(verify_ingest_api_key),
    db: Session = Depends(get_db),
) -> IngestResponse:
    service = IngestionService(Path(settings.data_dir))
    result = service.ingest_all(db)

    return IngestResponse(
        files_processed=result.files_processed,
        rows_read=result.rows_read,
        rows_inserted=result.rows_inserted,
        rows_updated=result.rows_updated,
        rows_skipped=result.rows_skipped,
        files=[
            IngestFileResult(
                filename=file.filename,
                rows_read=file.rows_read,
                rows_inserted=file.rows_inserted,
                rows_updated=file.rows_updated,
                rows_skipped=file.rows_skipped,
                errors=file.errors,
            )
            for file in result.files
        ],
        errors=result.errors,
    )
